import json
import os
import aiofiles
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar
from datetime import datetime
from uuid import UUID, uuid4
import asyncio
from threading import Lock

from app.core.config import settings

T = TypeVar('T')

BASE_DIR = Path(settings.DATA_DIR).expanduser()
BASE_DIR.mkdir(parents=True, exist_ok=True)

_FILE_LOCKS: Dict[str, Lock] = {}
_GLOBAL_LOCK = Lock()


def _get_lock(filepath: str) -> Lock:
    with _GLOBAL_LOCK:
        if filepath not in _FILE_LOCKS:
            _FILE_LOCKS[filepath] = Lock()
        return _FILE_LOCKS[filepath]


async def _read_json(filepath: Path) -> Any:
    if not filepath.exists():
        return None
    lock = _get_lock(str(filepath))
    with lock:
        async with aiofiles.open(filepath, 'r') as f:
            content = await f.read()
            return json.loads(content) if content else None


async def _write_json(filepath: Path, data: Any) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_lock(str(filepath))
    with lock:
        async with aiofiles.open(filepath, 'w') as f:
            await f.write(json.dumps(data, default=_json_default, indent=2))


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, UUID)):
        return str(obj)
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _uuid_to_str(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _uuid_to_str(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_uuid_to_str(v) for v in obj]
    return obj


class LocalStore:
    def __init__(self, entity_name: str, model_class: Type[T]):
        self.entity_name = entity_name
        self.model_class = model_class
        self.dir = BASE_DIR / entity_name
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.dir / "_index.json"
    
    def _record_path(self, id: UUID) -> Path:
        return self.dir / f"{id}.json"
    
    async def _load_index(self) -> Dict[str, Any]:
        return await _read_json(self.index_file) or {"ids": [], "by_field": {}}
    
    async def _save_index(self, index: Dict[str, Any]) -> None:
        await _write_json(self.index_file, index)
    
    async def create(self, obj: T) -> T:
        if not hasattr(obj, 'id') or obj.id is None:
            obj.id = uuid4()
        if not hasattr(obj, 'created_at') or obj.created_at is None:
            obj.created_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
        
        data = _uuid_to_str(obj.__dict__ if hasattr(obj, '__dict__') else obj)
        await _write_json(self._record_path(obj.id), data)
        
        index = await self._load_index()
        if str(obj.id) not in index["ids"]:
            index["ids"].append(str(obj.id))
        await self._save_index(index)
        
        return obj
    
    async def get(self, id: UUID) -> Optional[T]:
        data = await _read_json(self._record_path(id))
        if data is None:
            return None
        return self._deserialize(data)
    
    async def update(self, obj: T) -> T:
        obj.updated_at = datetime.utcnow()
        data = _uuid_to_str(obj.__dict__ if hasattr(obj, '__dict__') else obj)
        await _write_json(self._record_path(obj.id), data)
        return obj
    
    async def delete(self, id: UUID) -> bool:
        path = self._record_path(id)
        if path.exists():
            path.unlink()
            index = await self._load_index()
            if str(id) in index["ids"]:
                index["ids"].remove(str(id))
            await self._save_index(index)
            return True
        return False
    
    async def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        index = await self._load_index()
        ids = index["ids"][offset:offset + limit]
        results = []
        for id_str in ids:
            obj = await self.get(UUID(id_str))
            if obj:
                results.append(obj)
        return results
    
    async def filter(self, **kwargs) -> List[T]:
        index = await self._load_index()
        ids = index["ids"]
        results = []
        for id_str in ids:
            obj = await self.get(UUID(id_str))
            if obj and self._matches(obj, kwargs):
                results.append(obj)
        return results
    
    def _matches(self, obj: T, filters: Dict[str, Any]) -> bool:
        for key, value in filters.items():
            if hasattr(obj, key):
                obj_value = getattr(obj, key)
                if isinstance(value, list):
                    if obj_value not in value:
                        return False
                elif obj_value != value:
                    return False
            else:
                return False
        return True
    
    def _deserialize(self, data: Dict[str, Any]) -> T:
        for key, value in data.items():
            if isinstance(value, str):
                try:
                    if key.endswith('_at') or key in ('created_at', 'updated_at', 'expires_at', 'responded_at', 'completed_at', 'started_at'):
                        data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    elif key == 'id' or key.endswith('_id'):
                        data[key] = UUID(value)
                except (ValueError, AttributeError):
                    pass
        return self.model_class(**data)


class UserStore(LocalStore):
    def __init__(self):
        from app.models.local_models import User, UserRole
        super().__init__("users", User)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        results = await self.filter(email=email)
        return results[0] if results else None


class SessionStore(LocalStore):
    def __init__(self):
        from app.models.local_models import Session
        super().__init__("sessions", Session)
    
    async def get_by_token(self, token: str) -> Optional[Session]:
        results = await self.filter(session_token=token)
        return results[0] if results else None
    
    async def delete_expired(self) -> int:
        index = await self._load_index()
        deleted = 0
        now = datetime.utcnow()
        for id_str in index["ids"][:]:
            session = await self.get(UUID(id_str))
            if session and session.expires_at < now:
                await self.delete(session.id)
                deleted += 1
        return deleted


class TaskStore(LocalStore):
    def __init__(self):
        from app.models.local_models import Task, TaskStatus
        super().__init__("tasks", Task)
    
    async def get_by_user(self, user_id: UUID, status: str = None, limit: int = 20) -> List[Task]:
        tasks = await self.filter(user_id=user_id)
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]


class TaskStepStore(LocalStore):
    def __init__(self):
        from app.models.local_models import TaskStep
        super().__init__("task_steps", TaskStep)
    
    async def get_by_task(self, task_id: UUID) -> List[TaskStep]:
        steps = await self.filter(task_id=task_id)
        steps.sort(key=lambda s: s.step_number)
        return steps


class ApprovalStore(LocalStore):
    def __init__(self):
        from app.models.local_models import Approval, ApprovalStatus
        super().__init__("approvals", Approval)
    
    async def get_by_user(self, user_id: UUID, status: str = None, limit: int = 20) -> List[Approval]:
        approvals = await self.filter(user_id=user_id)
        if status:
            approvals = [a for a in approvals if a.status.value == status]
        approvals.sort(key=lambda a: a.created_at, reverse=True)
        return approvals[:limit]
    
    async def get_pending(self) -> List[Approval]:
        all_approvals = await self.list()
        return [a for a in all_approvals if a.status.value == "pending" and a.expires_at > datetime.utcnow()]


class MemoryStore(LocalStore):
    def __init__(self):
        from app.models.local_models import Memory, MemoryType
        super().__init__("memories", Memory)
    
    async def get_by_user_and_key(self, user_id: UUID, memory_type: MemoryType, key: str) -> Optional[Memory]:
        memories = await self.filter(user_id=user_id, type=memory_type, key=key)
        return memories[0] if memories else None
    
    async def search(self, user_id: UUID, query: str = "", types: List = None, limit: int = 10) -> List[Memory]:
        memories = await self.filter(user_id=user_id)
        if types:
            memories = [m for m in memories if m.type in types]
        if query:
            memories = [m for m in memories if query.lower() in m.key.lower() or query.lower() in str(m.value).lower()]
        memories.sort(key=lambda m: m.updated_at, reverse=True)
        return memories[:limit]


class SpendLimitStore(LocalStore):
    def __init__(self):
        from app.models.local_models import SpendLimit
        super().__init__("spend_limits", SpendLimit)
    
    async def get_or_create(self, user_id: UUID) -> SpendLimit:
        limits = await self.filter(user_id=user_id)
        if limits:
            return limits[0]
        from app.models.local_models import SpendLimit
        limit = SpendLimit(user_id=user_id)
        return await self.create(limit)


class TransactionStore(LocalStore):
    def __init__(self):
        from app.models.local_models import Transaction
        super().__init__("transactions", Transaction)
    
    async def get_daily_spend(self, user_id: UUID) -> float:
        transactions = await self.filter(user_id=user_id, status="completed")
        now = datetime.utcnow()
        day_ago = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return sum(t.amount for t in transactions if t.created_at >= day_ago)
    
    async def get_monthly_spend(self, user_id: UUID) -> float:
        transactions = await self.filter(user_id=user_id, status="completed")
        now = datetime.utcnow()
        month_ago = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return sum(t.amount for t in transactions if t.created_at >= month_ago)


class AuditLogStore(LocalStore):
    def __init__(self):
        from app.models.local_models import AuditLog
        super().__init__("audit_logs", AuditLog)


user_store = UserStore()
session_store = SessionStore()
task_store = TaskStore()
task_step_store = TaskStepStore()
approval_store = ApprovalStore()
memory_store = MemoryStore()
spend_limit_store = SpendLimitStore()
transaction_store = TransactionStore()
audit_log_store = AuditLogStore()


async def init_stores():
    await session_store.delete_expired()
    print(f"Local storage initialized at {BASE_DIR}")