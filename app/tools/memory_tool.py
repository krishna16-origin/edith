from typing import Any, Dict, List, Optional
from uuid import UUID
from app.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolCategory, ApprovalTier, ToolResult
from app.models import Memory, MemoryType
from app.storage.local_store import memory_store


class MemoryTool(BaseTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="memory",
            description="Read and write long-term memory (preferences, facts, bookings, contacts)",
            category=ToolCategory.MEMORY,
            approval_tier=ApprovalTier.TIER_1_READONLY,
            parameters=[
                ToolParameter(name="action", type="string", description="Action: read, write, delete, search, list", required=True),
                ToolParameter(name="memory_type", type="string", description="Type: preference, fact, conversation, booking, contact, document", required=False),
                ToolParameter(name="key", type="string", description="Memory key", required=False),
                ToolParameter(name="value", type="object", description="Memory value (for write)", required=False),
                ToolParameter(name="query", type="string", description="Search query", required=False),
                ToolParameter(name="tags", type="array", description="Tags for filtering", required=False),
                ToolParameter(name="limit", type="integer", description="Max results", required=False, default=10),
                ToolParameter(name="user_id", type="string", description="User ID (for cross-user access)", required=False),
            ],
            returns={"type": "object", "properties": {"memories": {"type": "array"}, "memory": {"type": "object"}}},
            examples=[
                {"action": "write", "memory_type": "preference", "key": "seat", "value": {"preference": "aisle"}},
                {"action": "read", "memory_type": "preference", "key": "seat"},
                {"action": "search", "query": "hotel", "limit": 5},
            ]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")
        user_id_str = kwargs.get("user_id")
        
        if not user_id_str:
            return ToolResult(success=False, error="user_id required")
        
        user_id = UUID(user_id_str)
        
        try:
            if action == "read":
                return await self._read(user_id, kwargs)
            elif action == "write":
                return await self._write(user_id, kwargs)
            elif action == "delete":
                return await self._delete(user_id, kwargs)
            elif action == "search":
                return await self._search(user_id, kwargs)
            elif action == "list":
                return await self._list(user_id, kwargs)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _read(self, user_id: UUID, kwargs: Dict) -> ToolResult:
        memory_type = kwargs.get("memory_type")
        key = kwargs.get("key")
        
        if not memory_type or not key:
            return ToolResult(success=False, error="memory_type and key required")
        
        memory = await memory_store.get_by_user_and_key(user_id, MemoryType(memory_type), key)
        
        if not memory:
            return ToolResult(success=False, error="Memory not found")
        
        return ToolResult(success=True, data={
            "memory": {
                "id": str(memory.id),
                "type": memory.type.value,
                "key": memory.key,
                "value": memory.value,
                "confidence": memory.confidence,
                "source": memory.source,
                "tags": memory.tags,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat(),
            }
        })
    
    async def _write(self, user_id: UUID, kwargs: Dict) -> ToolResult:
        memory_type = kwargs.get("memory_type")
        key = kwargs.get("key")
        value = kwargs.get("value")
        confidence = kwargs.get("confidence", 1.0)
        source = kwargs.get("source", "agent")
        tags = kwargs.get("tags", [])
        
        if not memory_type or not key or value is None:
            return ToolResult(success=False, error="memory_type, key, and value required")
        
        existing = await memory_store.get_by_user_and_key(user_id, MemoryType(memory_type), key)
        
        if existing:
            existing.value = value
            existing.confidence = confidence
            existing.source = source
            existing.tags = tags
            memory = await memory_store.update(existing)
        else:
            memory = Memory(
                user_id=user_id,
                type=MemoryType(memory_type),
                key=key,
                value=value,
                confidence=confidence,
                source=source,
                tags=tags,
            )
            memory = await memory_store.create(memory)
        
        return ToolResult(success=True, data={
            "memory": {
                "id": str(memory.id),
                "type": memory.type.value,
                "key": memory.key,
                "value": memory.value,
            }
        })
    
    async def _delete(self, user_id: UUID, kwargs: Dict) -> ToolResult:
        memory_type = kwargs.get("memory_type")
        key = kwargs.get("key")
        
        if not memory_type or not key:
            return ToolResult(success=False, error="memory_type and key required")
        
        memory = await memory_store.get_by_user_and_key(user_id, MemoryType(memory_type), key)
        if not memory:
            return ToolResult(success=False, error="Memory not found")
        
        await memory_store.delete(memory.id)
        return ToolResult(success=True, data={"deleted": True})
    
    async def _search(self, user_id: UUID, kwargs: Dict) -> ToolResult:
        query = kwargs.get("query", "")
        limit = kwargs.get("limit", 10)
        tags = kwargs.get("tags", [])
        
        memory_types = None
        if tags:
            memory_types = [MemoryType(t) for t in tags if t in [mt.value for mt in MemoryType]]
        
        memories = await memory_store.search(user_id, query, memory_types, limit)
        
        return ToolResult(success=True, data={
            "memories": [
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
        })
    
    async def _list(self, user_id: UUID, kwargs: Dict) -> ToolResult:
        memory_type_str = kwargs.get("memory_type")
        limit = kwargs.get("limit", 50)
        
        memory_type = MemoryType(memory_type_str) if memory_type_str else None
        memories = await memory_store.search(user_id, "", [memory_type] if memory_type else None, limit)
        
        return ToolResult(success=True, data={
            "memories": [
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
        })


memory_tool = MemoryTool()