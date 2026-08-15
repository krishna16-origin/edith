from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from typing import Optional, List
import structlog

from app.auth import get_current_active_user
from app.models import Memory, MemoryType
from app.schemas import (
    MemoryCreate, MemoryUpdate, MemoryResponse, MemoryType as SchemaMemoryType
)
from app.storage.local_store import memory_store
from app.memory.service import memory_service

logger = structlog.get_logger()
router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.post("", response_model=MemoryResponse)
async def create_memory(
    request: MemoryCreate,
    current_user: User = Depends(get_current_active_user),
):
    existing = await memory_store.get_by_user_and_key(current_user.id, MemoryType(request.type.value), request.key)
    
    if existing:
        existing.value = request.value
        existing.confidence = request.confidence
        existing.source = request.source
        existing.tags = request.tags
        memory = await memory_store.update(existing)
    else:
        memory = Memory(
            user_id=current_user.id,
            type=MemoryType(request.type.value),
            key=request.key,
            value=request.value,
            confidence=request.confidence,
            source=request.source,
            tags=request.tags,
        )
        memory = await memory_store.create(memory)
    
    logger.info("memory_created", user_id=str(current_user.id), key=request.key, type=request.type.value)
    
    return MemoryResponse.from_orm(memory)


@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    type: Optional[SchemaMemoryType] = None,
    key: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
):
    memory_type = MemoryType(type.value) if type else None
    memories = await memory_store.search(current_user.id, key or "", [memory_type] if memory_type else None, limit)
    return [MemoryResponse.from_orm(m) for m in memories]


@router.get("/search", response_model=List[MemoryResponse])
async def search_memories(
    q: str,
    type: Optional[SchemaMemoryType] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user)
):
    types = [MemoryType(type.value)] if type else None
    results = await memory_service.search_long_term(current_user.id, q, types, limit)
    
    return [
        MemoryResponse(
            id=UUID(r["id"]),
            type=SchemaMemoryType(r["type"]),
            key=r["key"],
            value=r["value"],
            confidence=r["confidence"],
            source="",
            tags=r["tags"],
            created_at=r["updated_at"],
            updated_at=r["updated_at"],
        )
        for r in results
    ]


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    memory = await memory_store.get(memory_id)
    
    if not memory or memory.user_id != current_user.id:
        raise HTTPException(404, "Memory not found")
    
    return MemoryResponse.from_orm(memory)


@router.patch("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: UUID,
    request: MemoryUpdate,
    current_user: User = Depends(get_current_active_user),
):
    memory = await memory_store.get(memory_id)
    
    if not memory or memory.user_id != current_user.id:
        raise HTTPException(404, "Memory not found")
    
    if request.value is not None:
        memory.value = request.value
    if request.confidence is not None:
        memory.confidence = request.confidence
    if request.tags is not None:
        memory.tags = request.tags
    
    await memory_store.update(memory)
    
    return MemoryResponse.from_orm(memory)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    memory = await memory_store.get(memory_id)
    
    if not memory or memory.user_id != current_user.id:
        raise HTTPException(404, "Memory not found")
    
    await memory_store.delete(memory_id)
    
    return {"deleted": True, "memory_id": str(memory_id)}


@router.get("/preferences/all")
async def get_preferences(
    current_user: User = Depends(get_current_active_user)
):
    prefs = await memory_service.get_user_preferences(current_user.id)
    return {"preferences": prefs}