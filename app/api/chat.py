from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from uuid import UUID
from typing import Optional
import structlog

from app.auth import get_current_active_user, create_user_session, validate_session
from app.models import User, Session, Task, TaskStatus
from app.schemas import (
    ChatRequest, ChatResponse, ChatMessage,
    TaskCreate, TaskResponse, WebSocketMessage
)
from app.services.orchestrator import orchestrator
from app.tools import get_tool_registry
from app.storage.local_store import task_store, task_step_store, session_store

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
):
    session_id = request.session_id
    
    if session_id:
        session = await validate_session(session_id)
        if not session or session.user_id != current_user.id:
            raise HTTPException(401, "Invalid session")
    else:
        session = await create_user_session(current_user)
        session_id = session.session_token
    
    task_id = None
    if request.context and request.context.get("task_id"):
        task_id = UUID(request.context["task_id"])
    
    result = await orchestrator.process_message(
        user_id=current_user.id,
        message=request.message,
        session_id=session_id,
        task_id=task_id,
        stream=request.stream
    )
    
    if request.stream:
        return {"stream": True, "session_id": session_id}
    
    return ChatResponse(
        response=result.get("response", ""),
        session_id=session_id,
        tool_calls=result.get("tool_calls"),
        requires_approval=result.get("requires_approval", False),
        approval_details=result.get("approval_details"),
        task_id=result.get("task_id"),
    )


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
):
    await websocket.accept()
    
    session = await validate_session(session_id)
    if not session:
        await websocket.send_json({"type": "error", "content": "Invalid session"})
        await websocket.close()
        return
    
    logger.info("ws_connected", session_id=session_id, user_id=str(session.user_id))
    
    try:
        while True:
            data = await websocket.receive_json()
            msg = WebSocketMessage(**data)
            
            if msg.type == "chat":
                async for chunk in orchestrator.process_message(
                    user_id=session.user_id,
                    message=msg.content or "",
                    session_id=session_id,
                    task_id=UUID(msg.session_id) if msg.session_id else None,
                    stream=True
                ):
                    await websocket.send_json(chunk)
            
            elif msg.type == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=session_id)
    except Exception as e:
        logger.error("ws_error", session_id=session_id, error=str(e))
        await websocket.send_json({"type": "error", "content": str(e)})


@router.get("/tools")
async def list_tools(current_user: User = Depends(get_current_active_user)):
    registry = get_tool_registry()
    return {"tools": registry.list_tools()}


@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    request: TaskCreate,
    current_user: User = Depends(get_current_active_user),
):
    task = Task(
        user_id=current_user.id,
        goal=request.goal,
        status=TaskStatus.PENDING,
        context=request.context or {},
    )
    task = await task_store.create(task)
    
    return TaskResponse.from_orm(task)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    task = await task_store.get(task_id)
    
    if not task or task.user_id != current_user.id:
        raise HTTPException(404, "Task not found")
    
    steps = await task_step_store.get_by_task(task_id)
    task_response = TaskResponse.from_orm(task)
    task_response.steps = steps
    return task_response


@router.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    status: Optional[TaskStatus] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
):
    tasks = await task_store.get_by_user(current_user.id, status.value if status else None, limit)
    return [TaskResponse.from_orm(t) for t in tasks]


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    task = await task_store.get(task_id)
    
    if not task or task.user_id != current_user.id:
        raise HTTPException(404, "Task not found")
    
    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        raise HTTPException(400, "Task already finished")
    
    task.status = TaskStatus.CANCELLED
    await task_store.update(task)
    
    return {"status": "cancelled", "task_id": str(task_id)}