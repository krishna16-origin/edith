from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timedelta
import structlog

from app.models import Approval, ApprovalTier, ApprovalStatus, SpendLimit
from app.tools.base import ToolDefinition
from app.storage.local_store import spend_limit_store, approval_store, audit_log_store
from app.core.config import settings

logger = structlog.get_logger()


class ActionClassifier:
    TIER_1_ACTIONS = {
        "web_search", "browser", "calendar", "email",
        "memory", "credential_vault",
    }
    
    TIER_2_ACTIONS = {
        "email:draft", "calendar:create", "browser:click", "browser:type",
    }
    
    TIER_3_ACTIONS = {
        "phone_call", "payment", "email:send", "calendar:delete",
    }
    
    FINANCIAL_TOOLS = {"payment"}
    IRREVERSIBLE_TOOLS = {"phone_call"}
    
    @classmethod
    def classify(cls, tool_name: str, arguments: Dict[str, Any], tool_def: ToolDefinition) -> ApprovalTier:
        if tool_def.approval_tier:
            return tool_def.approval_tier
        
        action_key = f"{tool_name}:{arguments.get('action', '')}" if arguments.get('action') else tool_name
        
        if action_key in cls.TIER_3_ACTIONS or tool_name in cls.TIER_3_ACTIONS:
            return ApprovalTier.TIER_3_IRREVERSIBLE
        
        if action_key in cls.TIER_2_ACTIONS or tool_name in cls.TIER_2_ACTIONS:
            return ApprovalTier.TIER_2_REVERSIBLE
        
        if tool_name in cls.TIER_1_ACTIONS:
            return ApprovalTier.TIER_1_READONLY
        
        if tool_name in cls.FINANCIAL_TOOLS:
            amount = arguments.get("amount", 0)
            if amount > 0:
                return ApprovalTier.TIER_3_IRREVERSIBLE
        
        if tool_name in cls.IRREVERSIBLE_TOOLS:
            return ApprovalTier.TIER_3_IRREVERSIBLE
        
        return ApprovalTier.TIER_1_READONLY


class SpendLimitChecker:
    @staticmethod
    async def check_limit(user_id: UUID, amount: float, category: str) -> tuple[bool, str]:
        limit = await spend_limit_store.get_or_create(user_id)
        
        if category in limit.blocked_categories:
            return False, f"Category '{category}' is blocked"
        
        if amount > limit.per_transaction_limit:
            return False, f"Amount ${amount:.2f} exceeds per-transaction limit ${limit.per_transaction_limit:.2f}"
        
        daily_spend = await transaction_store.get_daily_spend(user_id)
        if daily_spend + amount > limit.per_day_limit:
            return False, f"Daily spend limit would be exceeded (${daily_spend:.2f} + ${amount:.2f} > ${limit.per_day_limit:.2f})"
        
        monthly_spend = await transaction_store.get_monthly_spend(user_id)
        if monthly_spend + amount > limit.per_month_limit:
            return False, f"Monthly spend limit would be exceeded (${monthly_spend:.2f} + ${amount:.2f} > ${limit.per_month_limit:.2f})"
        
        return True, ""
    
    @staticmethod
    def requires_approval(amount: float, user_limit: SpendLimit) -> bool:
        if amount >= user_limit.require_approval_over:
            return True
        if amount <= user_limit.auto_approve_under:
            return False
        return True


class SafetyGate:
    def __init__(self):
        self.classifier = ActionClassifier()
        self.spend_checker = SpendLimitChecker()
    
    async def check_action(
        self,
        user_id: UUID,
        tool_name: str,
        arguments: Dict[str, Any],
        tool_def: ToolDefinition,
        task_id: UUID = None,
        step_id: UUID = None
    ) -> Dict[str, Any]:
        tier = self.classifier.classify(tool_name, arguments, tool_def)
        
        if tier == ApprovalTier.TIER_1_READONLY:
            return {"allowed": True, "tier": tier.value, "requires_approval": False}
        
        if tier == ApprovalTier.TIER_2_REVERSIBLE:
            await self._log_action(user_id, tool_name, arguments, tier, task_id, "auto_approved")
            return {"allowed": True, "tier": tier.value, "requires_approval": False, "report_after": True}
        
        if tier == ApprovalTier.TIER_3_IRREVERSIBLE:
            if tool_name == "payment":
                amount = arguments.get("amount", 0)
                category = arguments.get("category", "general")
                allowed, reason = await self.spend_checker.check_limit(user_id, amount, category)
                if not allowed:
                    return {"allowed": False, "tier": tier.value, "requires_approval": False, "error": reason}
                
                limit = await spend_limit_store.get_or_create(user_id)
                if not self.spend_checker.requires_approval(amount, limit):
                    return {"allowed": True, "tier": tier.value, "requires_approval": False}
            
            approval = await self._create_approval(user_id, tool_name, arguments, tier, task_id, step_id)
            return {
                "allowed": False,
                "tier": tier.value,
                "requires_approval": True,
                "approval_id": str(approval.id),
                "expires_at": approval.expires_at.isoformat(),
            }
        
        return {"allowed": False, "error": "Unknown tier"}
    
    async def _create_approval(
        self,
        user_id: UUID,
        tool_name: str,
        arguments: Dict[str, Any],
        tier: ApprovalTier,
        task_id: UUID = None,
        step_id: UUID = None
    ) -> Approval:
        approval = Approval(
            user_id=user_id,
            task_id=task_id,
            step_id=step_id,
            tier=tier,
            action_type=tool_name,
            action_details=arguments,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        return await approval_store.create(approval)
    
    async def process_approval(self, approval_id: UUID, approved: bool, user_input: str = None) -> Dict[str, Any]:
        approval = await approval_store.get(approval_id)
        
        if not approval:
            return {"success": False, "error": "Approval not found"}
        
        if approval.status != ApprovalStatus.PENDING:
            return {"success": False, "error": f"Approval already {approval.status.value}"}
        
        if datetime.utcnow() > approval.expires_at:
            approval.status = ApprovalStatus.EXPIRED
            await approval_store.update(approval)
            return {"success": False, "error": "Approval expired"}
        
        approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        approval.user_response = user_input
        approval.responded_at = datetime.utcnow()
        await approval_store.update(approval)
        
        await self._log_action(
            approval.user_id,
            approval.action_type,
            approval.action_details,
            approval.tier,
            approval.task_id,
            "approved" if approved else "rejected"
        )
        
        return {
            "success": True,
            "approved": approved,
            "approval_id": str(approval_id),
        }
    
    async def _log_action(
        self,
        user_id: UUID,
        action: str,
        details: Dict,
        tier: ApprovalTier,
        task_id: UUID = None,
        result: str = "pending"
    ):
        from app.models import AuditLog
        log = AuditLog(
            user_id=user_id,
            task_id=task_id,
            action=action,
            details=details,
            result=result,
        )
        await audit_log_store.create(log)


safety_gate = SafetyGate()