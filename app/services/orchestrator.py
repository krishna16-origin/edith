import json
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime
from uuid import UUID
import structlog
from openai import AsyncOpenAI

from app.core.config import settings
from app.tools.base import tool_registry, ToolDefinition
from app.tools import get_tool_registry
from app.memory.service import memory_service
from app.safety.gate import safety_gate
from app.storage.local_store import audit_log_store
from app.models import AuditLog

logger = structlog.get_logger()


class Orchestrator:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
        ) if settings.NVIDIA_API_KEY else None
        self.tool_registry = get_tool_registry()
    
    def _get_system_prompt(self, user_id: UUID, long_term_memories: List[Dict]) -> str:
        tools = self.tool_registry.list_tools()
        tool_descriptions = []
        for t in tools:
            params = ", ".join([f"{p.name}: {p.type}" for p in t.parameters])
            tool_descriptions.append(f"- {t.name}({params}): {t.description}")
        
        memory_str = ""
        if long_term_memories:
            memory_str = "\nUser preferences/memories:\n"
            for m in long_term_memories:
                memory_str += f"- {m['type']}: {m['key']} = {m['value']}\n"
        
        return f"""You are EDITH, a general-purpose personal AI assistant. You help users accomplish tasks by breaking them into steps and using tools.

Available tools:
{chr(10).join(tool_descriptions)}

{memory_str}

Rules:
1. Always think step by step. Break complex goals into discrete tool calls.
2. Use the right tool for the job. Prefer official APIs over browser automation.
3. For multi-step tasks, create a plan first, then execute steps.
4. After each tool call, analyze the result before deciding the next step.
5. If a tool fails, try an alternative approach or ask the user for clarification.
6. Never make irreversible commitments (payments, bookings, promises) without explicit user approval.
7. Be concise in your responses to the user.
8. If you need information from the user, ask a specific question.
9. Track task state so you can resume after interruptions.
10. Disclose when you're taking actions on the user's behalf.

Response format:
- For tool calls: Return a JSON object with "tool_calls" array
- For user responses: Return a JSON object with "response" string
- If waiting for approval: Return "awaiting_approval" with details
- If task complete: Return "completed" with result summary

Example tool call:
{{
  "tool_calls": [
    {{
      "id": "call_1",
      "name": "web_search",
      "arguments": {{"query": "flights NYC to London", "num_results": 5}}
    }}
  ]
}}

Example user response:
{{
  "response": "I found several flights. The cheapest is $450 on British Airways."
}}

Example awaiting approval:
{{
  "awaiting_approval": {{
    "action": "Book British Airways flight for $450",
    "details": {{"flight_id": "BA123", "price": 450}},
    "tier": "tier_3_irreversible"
  }}
}}"""
    
    async def _call_llm(self, messages: List[Dict], model: str = None, stream: bool = False) -> AsyncGenerator[str, None] | str:
        if not self.client:
            return "Error: NVIDIA API key not configured"
        
        model = model or settings.DEFAULT_MODEL
        
        if stream:
            async for chunk in self._stream_openai(messages, model):
                yield chunk
        else:
            resp = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=settings.TEMPERATURE,
                max_tokens=settings.MAX_TOKENS,
            )
            return resp.choices[0].message.content
    
    async def _stream_openai(self, messages: List[Dict], model: str) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=settings.TEMPERATURE,
            max_tokens=settings.MAX_TOKENS,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def process_message(
        self,
        user_id: UUID,
        message: str,
        session_id: str,
        task_id: UUID = None,
        stream: bool = False
    ) -> AsyncGenerator[Dict, None] | Dict:
        long_term_memories = await memory_service.search_long_term(user_id, "", limit=20)
        system_prompt = self._get_system_prompt(user_id, long_term_memories)
        
        short_term = await memory_service.get_short_term(UUID(task_id)) if task_id else {}
        conversation = short_term.get("conversation", [])
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation[-20:])
        messages.append({"role": "user", "content": message})
        
        if stream:
            async for chunk in self._stream_response(messages, user_id, session_id, task_id):
                yield chunk
        else:
            response = await self._call_llm(messages)
            result = await self._handle_llm_response(response, user_id, session_id, task_id, message)
            await memory_service.add_conversation_turn(UUID(task_id), "assistant", result.get("response", ""), result.get("tool_calls"))
            return result
    
    async def _stream_response(self, messages: List[Dict], user_id: UUID, session_id: str, task_id: UUID) -> AsyncGenerator[Dict, None]:
        full_response = ""
        async for chunk in self._call_llm(messages, stream=True):
            full_response += chunk
            yield {"type": "token", "content": chunk}
        
        result = await self._handle_llm_response(full_response, user_id, session_id, task_id, messages[-1]["content"])
        await memory_service.add_conversation_turn(UUID(task_id), "assistant", result.get("response", ""), result.get("tool_calls"))
        yield {"type": "complete", "data": result}
    
    async def _handle_llm_response(self, response: str, user_id: UUID, session_id: str, task_id: UUID, user_message: str) -> Dict:
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            return {"response": response, "session_id": session_id}
        
        if "tool_calls" in parsed:
            return await self._execute_tool_calls(parsed["tool_calls"], user_id, session_id, task_id)
        
        if "awaiting_approval" in parsed:
            return {
                "response": "Awaiting your approval...",
                "session_id": session_id,
                "requires_approval": True,
                "approval_details": parsed["awaiting_approval"],
            }
        
        if "completed" in parsed:
            return {
                "response": parsed["completed"].get("summary", "Task completed"),
                "session_id": session_id,
                "task_id": str(task_id) if task_id else None,
            }
        
        return {"response": parsed.get("response", response), "session_id": session_id}
    
    async def _execute_tool_calls(self, tool_calls: List[Dict], user_id: UUID, session_id: str, task_id: UUID) -> Dict:
        results = []
        tool_call_objects = []
        
        for tc in tool_calls:
            tool_name = tc.get("name")
            arguments = tc.get("arguments", {})
            call_id = tc.get("id", str(uuid.uuid4()))
            
            tool = self.tool_registry.get(tool_name)
            if not tool:
                results.append({"tool_call_id": call_id, "name": tool_name, "error": "Tool not found"})
                continue
            
            safety_check = await safety_gate.check_action(user_id, tool_name, arguments, tool.definition, UUID(task_id) if task_id else None)
            
            if not safety_check.get("allowed", False):
                if safety_check.get("requires_approval"):
                    return {
                        "response": "This action requires your approval.",
                        "session_id": session_id,
                        "requires_approval": True,
                        "approval_details": {
                            "action": f"Run {tool_name}",
                            "details": arguments,
                            "tier": safety_check["tier"],
                            "approval_id": safety_check.get("approval_id"),
                        },
                    }
                else:
                    results.append({"tool_call_id": call_id, "name": tool_name, "error": safety_check.get("error", "Not allowed")})
                    continue
            
            tool_result = await tool.execute(**arguments)
            results.append({
                "tool_call_id": call_id,
                "name": tool_name,
                "result": tool_result.data if tool_result.success else None,
                "error": tool_result.error,
            })
            
            tool_call_objects.append({
                "id": call_id,
                "name": tool_name,
                "arguments": arguments,
            })
            
            if safety_check.get("report_after"):
                await self._log_action(user_id, tool_name, arguments, tool_result, UUID(task_id) if task_id else None)
        
        await memory_service.add_conversation_turn(UUID(task_id), "assistant", "", tool_call_objects)
        
        messages = [
            {"role": "system", "content": self._get_system_prompt(user_id, await memory_service.search_long_term(user_id, "", limit=20))},
            {"role": "user", "content": "Tool results:"},
            {"role": "assistant", "content": json.dumps(results)},
        ]
        
        followup = await self._call_llm(messages)
        return await self._handle_llm_response(followup, user_id, session_id, task_id, "")
    
    async def _log_action(self, user_id: UUID, tool_name: str, arguments: Dict, result: Any, task_id: UUID):
        log = AuditLog(
            user_id=user_id,
            task_id=task_id,
            action=tool_name,
            details={"arguments": arguments, "result": result.data if hasattr(result, 'data') else str(result)},
            result="success" if (hasattr(result, 'success') and result.success) else "error",
        )
        await audit_log_store.create(log)


orchestrator = Orchestrator()