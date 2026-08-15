from fastapi import APIRouter, Depends, HTTPException
import structlog

from app.auth import get_current_active_user
from app.storage.local_store import spend_limit_store
from app.schemas import SpendLimitCreate, SpendLimitResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/api/spend", tags=["spend"])


@router.get("/limits", response_model=SpendLimitResponse)
async def get_spend_limits(
    current_user: User = Depends(get_current_active_user),
):
    limit = await spend_limit_store.get_or_create(current_user.id)
    return SpendLimitResponse.from_orm(limit)


@router.post("/limits", response_model=SpendLimitResponse)
async def update_spend_limits(
    request: SpendLimitCreate,
    current_user: User = Depends(get_current_active_user),
):
    limit = await spend_limit_store.get_or_create(current_user.id)
    
    limit.per_transaction_limit = request.per_transaction_limit
    limit.per_day_limit = request.per_day_limit
    limit.per_month_limit = request.per_month_limit
    limit.auto_approve_under = request.auto_approve_under
    limit.require_approval_over = request.require_approval_over
    limit.blocked_categories = request.blocked_categories
    
    await spend_limit_store.update(limit)
    
    return SpendLimitResponse.from_orm(limit)