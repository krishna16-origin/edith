from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
import asyncio
import structlog

from app.models import Task, TaskStep, TaskStatus, TaskStepStatus
from app.services.orchestrator import orchestrator
from app.tools import get_tool_registry
from app.safety.gate import safety_gate
from app.storage.local_store import task_store, task_step_store

logger = structlog.get_logger()


class TaskProcessor:
    def __init__(self):
        self._running_tasks: Dict[UUID, asyncio.Task] = {}
    
    async def start_task(self, task_id: UUID):
        if task_id in self._running_tasks:
            return
        
        task = asyncio.create_task(self._run_task(task_id))
        self._running_tasks[task_id] = task
        logger.info("task_started", task_id=str(task_id))
    
    async def _run_task(self, task_id: UUID):
        task = await task_store.get(task_id)
        
        if not task:
            logger.error("task_not_found", task_id=str(task_id))
            return
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        await task_store.update(task)
        
        try:
            await self._execute_plan(task_id)
        except Exception as e:
            logger.error("task_failed", task_id=str(task_id), error=str(e))
            task = await task_store.get(task_id)
            if task:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.utcnow()
                await task_store.update(task)
        finally:
            self._running_tasks.pop(task_id, None)
    
    async def _execute_plan(self, task_id: UUID):
        task = await task_store.get(task_id)
        
        if not task or not task.plan:
            return
        
        steps = task.plan.get("steps", [])
        tool_registry = get_tool_registry()
        
        for i, step_plan in enumerate(steps):
            task = await task_store.get(task_id)
            if not task or task.status == TaskStatus.CANCELLED:
                return
            
            step = TaskStep(
                task_id=task_id,
                step_number=i,
                tool_name=step_plan["tool"],
                arguments=step_plan.get("arguments", {}),
                status=TaskStepStatus.RUNNING,
                started_at=datetime.utcnow(),
            )
            step = await task_step_store.create(step)
            
            task.current_step = i
            await task_store.update(task)
            
            tool = tool_registry.get(step_plan["tool"])
            if not tool:
                step.status = TaskStepStatus.FAILED
                step.error = f"Tool not found: {step_plan['tool']}"
                step.completed_at = datetime.utcnow()
                await task_step_store.update(step)
                continue
            
            safety_check = await safety_gate.check_action(
                task.user_id,
                step_plan["tool"],
                step_plan.get("arguments", {}),
                tool.definition,
                task_id,
                step.id
            )
            
            if not safety_check.get("allowed", False):
                if safety_check.get("requires_approval"):
                    task = await task_store.get(task_id)
                    if task:
                        task.status = TaskStatus.WAITING_APPROVAL
                        await task_store.update(task)
                    step.approval_id = UUID(safety_check["approval_id"])
                    step.status = TaskStepStatus.FAILED
                    step.error = "Waiting for approval"
                    await task_step_store.update(step)
                    return
                else:
                    step.status = TaskStepStatus.FAILED
                    step.error = safety_check.get("error", "Not allowed")
                    step.completed_at = datetime.utcnow()
                    await task_step_store.update(step)
                    continue
            
            result = await tool.execute(**step_plan.get("arguments", {}))
            
            step.result = result.data if result.success else None
            step.error = result.error
            step.status = TaskStepStatus.COMPLETED if result.success else TaskStepStatus.FAILED
            step.completed_at = datetime.utcnow()
            await task_step_store.update(step)
            
            if not result.success:
                task = await task_store.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.error = f"Step {i} failed: {result.error}"
                    task.completed_at = datetime.utcnow()
                    await task_store.update(task)
                return
        
        task = await task_store.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.result = {"steps_completed": len(steps)}
            await task_store.update(task)
        
        logger.info("task_completed", task_id=str(task_id))
    
    def cancel_task(self, task_id: UUID):
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            self._running_tasks.pop(task_id, None)
            logger.info("task_cancelled", task_id=str(task_id))


task_processor = TaskProcessor()