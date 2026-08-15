import stripe
from typing import Any, Dict, List, Optional
from app.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolCategory, ApprovalTier, ToolResult
from app.core.config import settings


class PaymentTool(BaseTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="payment",
            description="Process payments, create payment intents, manage payment methods",
            category=ToolCategory.PAYMENT,
            approval_tier=ApprovalTier.TIER_3_IRREVERSIBLE,
            parameters=[
                ToolParameter(name="action", type="string", description="Action: create_intent, confirm, refund, get_method, attach_method", required=True),
                ToolParameter(name="amount", type="number", description="Amount in smallest currency unit (cents)", required=False),
                ToolParameter(name="currency", type="string", description="Currency code (USD, EUR, etc.)", required=False, default="usd"),
                ToolParameter(name="payment_method_id", type="string", description="Payment method ID", required=False),
                ToolParameter(name="customer_id", type="string", description="Stripe customer ID", required=False),
                ToolParameter(name="payment_intent_id", type="string", description="Payment intent ID", required=False),
                ToolParameter(name="description", type="string", description="Payment description", required=False),
                ToolParameter(name="metadata", type="object", description="Additional metadata", required=False),
                ToolParameter(name="confirm", type="boolean", description="Auto-confirm payment intent", required=False, default=False),
            ],
            returns={"type": "object", "properties": {"payment_intent": {"type": "object"}, "status": {"type": "string"}}},
            examples=[
                {"action": "create_intent", "amount": 5000, "currency": "usd", "description": "Hotel booking"},
                {"action": "confirm", "payment_intent_id": "pi_123", "payment_method_id": "pm_123"},
            ]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        if not settings.STRIPE_SECRET_KEY:
            return ToolResult(success=False, error="Stripe not configured")
        
        action = kwargs.get("action")
        
        try:
            if action == "create_intent":
                return await self._create_intent(kwargs)
            elif action == "confirm":
                return await self._confirm(kwargs)
            elif action == "refund":
                return await self._refund(kwargs)
            elif action == "get_method":
                return await self._get_method(kwargs)
            elif action == "attach_method":
                return await self._attach_method(kwargs)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except stripe.error.StripeError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _create_intent(self, kwargs: Dict) -> ToolResult:
        amount = kwargs.get("amount")
        currency = kwargs.get("currency", "usd")
        customer_id = kwargs.get("customer_id")
        description = kwargs.get("description")
        metadata = kwargs.get("metadata", {})
        confirm = kwargs.get("confirm", False)
        
        if not amount:
            return ToolResult(success=False, error="Amount required")
        
        params = {
            "amount": int(amount),
            "currency": currency,
            "description": description,
            "metadata": metadata,
            "automatic_payment_methods": {"enabled": True},
        }
        
        if customer_id:
            params["customer"] = customer_id
        
        if confirm:
            params["confirm"] = True
            payment_method = kwargs.get("payment_method_id")
            if payment_method:
                params["payment_method"] = payment_method
        
        intent = stripe.PaymentIntent.create(**params)
        
        return ToolResult(success=True, data={
            "payment_intent_id": intent.id,
            "client_secret": intent.client_secret,
            "status": intent.status,
            "amount": intent.amount,
            "currency": intent.currency,
        })
    
    async def _confirm(self, kwargs: Dict) -> ToolResult:
        payment_intent_id = kwargs.get("payment_intent_id")
        payment_method_id = kwargs.get("payment_method_id")
        
        if not payment_intent_id:
            return ToolResult(success=False, error="Payment intent ID required")
        
        params = {}
        if payment_method_id:
            params["payment_method"] = payment_method_id
        
        intent = stripe.PaymentIntent.confirm(payment_intent_id, **params)
        
        return ToolResult(success=True, data={
            "payment_intent_id": intent.id,
            "status": intent.status,
        })
    
    async def _refund(self, kwargs: Dict) -> ToolResult:
        payment_intent_id = kwargs.get("payment_intent_id")
        amount = kwargs.get("amount")
        
        if not payment_intent_id:
            return ToolResult(success=False, error="Payment intent ID required")
        
        params = {"payment_intent": payment_intent_id}
        if amount:
            params["amount"] = int(amount)
        
        refund = stripe.Refund.create(**params)
        
        return ToolResult(success=True, data={
            "refund_id": refund.id,
            "status": refund.status,
            "amount": refund.amount,
        })
    
    async def _get_method(self, kwargs: Dict) -> ToolResult:
        payment_method_id = kwargs.get("payment_method_id")
        
        if not payment_method_id:
            return ToolResult(success=False, error="Payment method ID required")
        
        pm = stripe.PaymentMethod.retrieve(payment_method_id)
        
        return ToolResult(success=True, data={
            "payment_method_id": pm.id,
            "type": pm.type,
            "card": pm.card if pm.type == "card" else None,
        })
    
    async def _attach_method(self, kwargs: Dict) -> ToolResult:
        payment_method_id = kwargs.get("payment_method_id")
        customer_id = kwargs.get("customer_id")
        
        if not payment_method_id or not customer_id:
            return ToolResult(success=False, error="Payment method ID and customer ID required")
        
        pm = stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
        
        return ToolResult(success=True, data={
            "payment_method_id": pm.id,
            "customer_id": pm.customer,
        })


payment_tool = PaymentTool()