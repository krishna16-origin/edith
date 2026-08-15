import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID
from pathlib import Path
import aiofiles

from app.core.config import settings
from app.models import Memory, MemoryType


class MemoryService:
    def __init__(self):
        self.short_term_dir = Path(settings.DATA_DIR).expanduser() / "short_term_memory"
        self.short_term_dir.mkdir(parents=True, exist_ok=True)
    
    def _task_memory_path(self, task_id: UUID) -> Path:
        return self.short_term_dir / f"{task_id}.json"
    
    async def get_short_term(self, task_id: UUID) -> Dict[str, Any]:
        path = self._task_memory_path(task_id)
        if not path.exists():
            return {}
        async with aiofiles.open(path, 'r') as f:
            content = await f.read()
            return json.loads(content) if content else {}
    
    async def set_short_term(self, task_id: UUID, memory: Dict[str, Any], ttl: int = 3600) -> None:
        path = self._task_memory_path(task_id)
        async with aiofiles.open(path, 'w') as f:
            await f.write(json.dumps(memory, default=str))
    
    async def update_short_term(self, task_id: UUID, updates: Dict[str, Any]) -> None:
        memory = await self.get_short_term(task_id)
        memory.update(updates)
        await self.set_short_term(task_id, memory)
    
    async def clear_short_term(self, task_id: UUID) -> None:
        path = self._task_memory_path(task_id)
        if path.exists():
            path.unlink()
    
    async def add_conversation_turn(self, task_id: UUID, role: str, content: str, tool_calls: List = None) -> None:
        memory = await self.get_short_term(task_id)
        if "conversation" not in memory:
            memory["conversation"] = []
        memory["conversation"].append({
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(memory["conversation"]) > 50:
            memory["conversation"] = memory["conversation"][-50:]
        await self.set_short_term(task_id, memory)
    
    async def get_conversation_history(self, task_id: UUID, limit: int = 20) -> List[Dict]:
        memory = await self.get_short_term(task_id)
        conv = memory.get("conversation", [])
        return conv[-limit:]
    
    async def search_long_term(self, user_id: UUID, query: str, memory_types: List[MemoryType] = None, limit: int = 10) -> List[Dict]:
        from app.storage.local_store import memory_store
        
        memories = await memory_store.search(user_id, query, memory_types, limit)
        
        return [
            {
                "id": str(m.id),
                "type": m.type.value,
                "key": m.key,
                "value": m.value,
                "confidence": m.confidence,
                "tags": m.tags,
                "updated_at": m.updated_at.isoformat(),
            }
            for m in memories
        ]
    
    async def get_user_preferences(self, user_id: UUID) -> Dict[str, Any]:
        prefs = await self.search_long_term(user_id, "", [MemoryType.PREFERENCE], limit=100)
        return {p["key"]: p["value"] for p in prefs}
    
    async def close(self):
        pass


memory_service = MemoryService()