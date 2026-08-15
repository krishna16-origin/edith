from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, EmailStr


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Session(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    goal: str
    status: TaskStatus = TaskStatus.PENDING
    plan: Optional[Dict[str, Any]] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    current_step: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None


class TaskStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskStep(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    step_number: int
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    status: TaskStepStatus = TaskStepStatus.PENDING
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approval_id: Optional[UUID] = None


class ApprovalTier(str, Enum):
    TIER_1_READONLY = "tier_1_readonly"
    TIER_2_REVERSIBLE = "tier_2_reversible"
    TIER_3_IRREVERSIBLE = "tier_3_irreversible"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Approval(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    task_id: Optional[UUID] = None
    step_id: Optional[UUID] = None
    tier: ApprovalTier
    action_type: str
    action_details: Dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    user_response: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    responded_at: Optional[datetime] = None
    expires_at: datetime


class MemoryType(str, Enum):
    PREFERENCE = "preference"
    FACT = "fact"
    CONVERSATION = "conversation"
    BOOKING = "booking"
    CONTACT = "contact"
    DOCUMENT = "document"


class Memory(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    type: MemoryType
    key: str
    value: Dict[str, Any]
    confidence: float = 1.0
    source: str = "user"
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class SpendLimit(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    per_transaction_limit: float = 500.0
    per_day_limit: float = 2000.0
    per_month_limit: float = 10000.0
    auto_approve_under: float = 50.0
    require_approval_over: float = 200.0
    blocked_categories: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Transaction(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    approval_id: Optional[UUID] = None
    amount: float
    currency: str = "USD"
    category: str
    description: str
    status: str = "pending"
    stripe_payment_intent_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class AuditLog(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    task_id: Optional[UUID] = None
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
    result: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)