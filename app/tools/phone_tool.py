import asyncio
from typing import Any, Dict, List, Optional
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Say, Gather, Record, Pause
from app.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolCategory, ApprovalTier, ToolResult
from app.core.config import settings


class PhoneTool(BaseTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.client = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            self.client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="phone_call",
            description="Make outbound phone calls and conduct conversations",
            category=ToolCategory.PHONE,
            approval_tier=ApprovalTier.TIER_3_IRREVERSIBLE,
            parameters=[
                ToolParameter(name="to", type="string", description="Phone number to call (E.164 format)", required=True),
                ToolParameter(name="goal", type="string", description="Goal for the call (e.g., 'book a table for 4 at 8pm')", required=True),
                ToolParameter(name="constraints", type="object", description="Hard limits for the call", required=False),
                ToolParameter(name="script", type="string", description="Optional script to follow", required=False),
                ToolParameter(name="max_duration", type="integer", description="Maximum call duration in seconds", required=False, default=300),
            ],
            returns={"type": "object", "properties": {"call_sid": {"type": "string"}, "status": {"type": "string"}, "transcript": {"type": "string"}, "outcome": {"type": "string"}}},
            examples=[
                {"to": "+15551234567", "goal": "Book a table for 4 at 8pm", "constraints": {"max_deposit": 50}},
            ]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        if not self.client:
            return ToolResult(success=False, error="Twilio not configured")
        
        to = kwargs.get("to")
        goal = kwargs.get("goal")
        constraints = kwargs.get("constraints", {})
        script = kwargs.get("script")
        max_duration = kwargs.get("max_duration", 300)
        
        if not to or not goal:
            return ToolResult(success=False, error="to and goal required")
        
        try:
            call = self.client.calls.create(
                to=to,
                from_=settings.TWILIO_PHONE_NUMBER,
                url=f"{settings.WEBHOOK_BASE_URL}/voice/start",
                method="POST",
                status_callback=f"{settings.WEBHOOK_BASE_URL}/voice/status",
                status_callback_method="POST",
                timeout=max_duration,
                record=True,
                recording_channels="dual",
            )
            
            return ToolResult(success=True, data={
                "call_sid": call.sid,
                "status": call.status,
                "goal": goal,
                "constraints": constraints,
            })
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def generate_twiml(self, goal: str, constraints: Dict, script: Optional[str] = None) -> str:
        response = VoiceResponse()
        
        response.say(
            "Hello, this is an AI assistant calling on behalf of a user. "
            "This call may be recorded for quality purposes.",
            voice="alice"
        )
        
        if script:
            response.say(script, voice="alice")
        else:
            response.say(f"My goal is to {goal}.", voice="alice")
        
        gather = Gather(
            input="speech",
            action="/voice/process",
            method="POST",
            speech_timeout="auto",
            language="en-US",
        )
        gather.say("How can I help you?", voice="alice")
        response.append(gather)
        
        return str(response)


phone_tool = PhoneTool()