from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import Optional
import structlog

from app.auth import get_current_active_user
from app.models import Approval, ApprovalStatus
from app.schemas import ApprovalRequest, ApprovalResponse, ApprovalStatus as SchemaApprovalStatus
from app.storage.local_store import approval_store
from app.safety.gate import safety_gate

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["approvals"])


@router.post("/approvals/{approval_id}", response_model=ApprovalResponse)
async def handle_approval(
    approval_id: UUID,
    request: ApprovalRequest,
    current_user: User = Depends(get_current_active_user),
):
    approval = await approval_store.get(approval_id)
    
    if not approval or approval.user_id != current_user.id:
        raise HTTPException(404, "Approval not found")
    
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(400, f"Approval already {approval.status.value}")
    
    from datetime import datetime
    if datetime.utcnow() > approval.expires_at:
        approval.status = ApprovalStatus.EXPIRED
        await approval_store.update(approval)
        raise HTTPException(400, "Approval expired")
    
    approval.status = ApprovalStatus.APPROVED if request.approved else ApprovalStatus.REJECTED
    approval.user_response = request.user_input
    approval.responded_at = datetime.utcnow()
    await approval_store.update(approval)
    
    logger.info("approval_processed", approval_id=str(approval_id), approved=request.approved)
    
    return ApprovalResponse.from_orm(approval)


@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_approvals(
    status: Optional[SchemaApprovalStatus] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
):
    approvals = await approval_store.get_by_user(current_user.id, status.value if status else None, limit)
    return [ApprovalResponse.from_orm(a) for a in approvals]


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    approval = await approval_store.get(approval_id)
    
    if not approval or approval.user_id != current_user.id:
        raise HTTPException(404, "Approval not found")
    
    return ApprovalResponse.from_orm(approval)