from fastapi import APIRouter, Depends, HTTPException, status
from datetime import timedelta
import structlog

from app.auth import (
    get_current_active_user, create_access_token, verify_password, get_password_hash,
    create_user_session, validate_session
)
from app.storage.local_store import user_store
from app.models import User, Session
from app.schemas import (
    UserCreate, UserResponse, UserUpdate, LoginRequest, Token, TokenData
)
from app.core.config import settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register(
    request: UserCreate,
):
    existing = await user_store.get_by_email(request.email)
    if existing:
        raise HTTPException(400, "Email already registered")
    
    user = User(
        email=request.email,
        full_name=request.full_name,
        hashed_password=get_password_hash(request.password),
    )
    user = await user_store.create(user)
    
    logger.info("user_registered", user_id=str(user.id), email=user.email)
    
    return UserResponse.from_orm(user)


@router.post("/login", response_model=Token)
async def login(
    request: LoginRequest,
):
    user = await user_store.get_by_email(request.email)
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(400, "Inactive user")
    
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    session = await create_user_session(user)
    
    logger.info("user_login", user_id=str(user.id))
    
    return Token(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user),
):
    sessions = await session_store.filter(user_id=current_user.id)
    for session in sessions:
        await session_store.delete(session.id)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return UserResponse.from_orm(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: UserUpdate,
    current_user: User = Depends(get_current_active_user),
):
    if request.full_name is not None:
        current_user.full_name = request.full_name
    if request.is_active is not None:
        current_user.is_active = request.is_active
    
    await user_store.update(current_user)
    
    return UserResponse.from_orm(current_user)


@router.post("/session", response_model=dict)
async def create_session(
    current_user: User = Depends(get_current_active_user),
):
    session = await create_user_session(current_user)
    return {"session_token": session.session_token, "expires_at": session.expires_at.isoformat()}


@router.get("/session/{session_token}")
async def check_session(
    session_token: str,
):
    session = await validate_session(session_token)
    if not session:
        raise HTTPException(401, "Invalid or expired session")
    
    user = await user_store.get(session.user_id)
    
    return {
        "valid": True,
        "user_id": str(session.user_id),
        "email": user.email if user else None,
        "expires_at": session.expires_at.isoformat(),
    }