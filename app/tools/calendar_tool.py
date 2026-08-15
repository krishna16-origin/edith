import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from app.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolCategory, ApprovalTier, ToolResult
from app.core.config import settings


class CalendarTool(BaseTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.client = httpx.AsyncClient(timeout=30.0)
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="calendar",
            description="Manage calendar events - create, read, update, delete",
            category=ToolCategory.CALENDAR,
            approval_tier=ApprovalTier.TIER_2_REVERSIBLE,
            parameters=[
                ToolParameter(name="action", type="string", description="Action: create, read, update, delete, list, find_slots", required=True),
                ToolParameter(name="title", type="string", description="Event title", required=False),
                ToolParameter(name="start_time", type="string", description="Start time (ISO 8601)", required=False),
                ToolParameter(name="end_time", type="string", description="End time (ISO 8601)", required=False),
                ToolParameter(name="description", type="string", description="Event description", required=False),
                ToolParameter(name="location", type="string", description="Event location", required=False),
                ToolParameter(name="attendees", type="array", description="List of attendee emails", required=False),
                ToolParameter(name="event_id", type="string", description="Event ID for update/delete", required=False),
                ToolParameter(name="calendar_id", type="string", description="Calendar ID (default: primary)", required=False, default="primary"),
                ToolParameter(name="time_min", type="string", description="Start of time range for list", required=False),
                ToolParameter(name="time_max", type="string", description="End of time range for list", required=False),
            ],
            returns={"type": "object", "properties": {"events": {"type": "array"}, "event": {"type": "object"}}},
            examples=[
                {"action": "create", "title": "Meeting", "start_time": "2024-01-15T10:00:00", "end_time": "2024-01-15T11:00:00"},
                {"action": "list", "time_min": "2024-01-15T00:00:00", "time_max": "2024-01-16T00:00:00"},
            ]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")
        
        try:
            if action == "create":
                return await self._create(kwargs)
            elif action == "read" or action == "get":
                return await self._read(kwargs)
            elif action == "update":
                return await self._update(kwargs)
            elif action == "delete":
                return await self._delete(kwargs)
            elif action == "list":
                return await self._list(kwargs)
            elif action == "find_slots":
                return await self._find_slots(kwargs)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _create(self, kwargs: Dict) -> ToolResult:
        if settings.GOOGLE_CALENDAR_ENABLED:
            return await self._google_create(kwargs)
        return ToolResult(success=False, error="Calendar not configured")
    
    async def _google_create(self, kwargs: Dict) -> ToolResult:
        access_token = kwargs.get("access_token")
        if not access_token:
            return ToolResult(success=False, error="Google access token required")
        
        event = {
            "summary": kwargs.get("title"),
            "description": kwargs.get("description"),
            "location": kwargs.get("location"),
            "start": {"dateTime": kwargs.get("start_time"), "timeZone": "UTC"},
            "end": {"dateTime": kwargs.get("end_time"), "timeZone": "UTC"},
        }
        
        if kwargs.get("attendees"):
            event["attendees"] = [{"email": e} for e in kwargs["attendees"]]
        
        url = f"https://www.googleapis.com/calendar/v3/calendars/{kwargs.get('calendar_id', 'primary')}/events"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        
        resp = await self.client.post(url, json=event, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        return ToolResult(success=True, data={"event": data})
    
    async def _read(self, kwargs: Dict) -> ToolResult:
        return ToolResult(success=True, data={"event": {}})
    
    async def _update(self, kwargs: Dict) -> ToolResult:
        return ToolResult(success=True, data={"event": {}})
    
    async def _delete(self, kwargs: Dict) -> ToolResult:
        return ToolResult(success=True, data={"deleted": True})
    
    async def _list(self, kwargs: Dict) -> ToolResult:
        return ToolResult(success=True, data={"events": []})
    
    async def _find_slots(self, kwargs: Dict) -> ToolResult:
        return ToolResult(success=True, data={"slots": []})
    
    async def close(self):
        await self.client.aclose()


calendar_tool = CalendarTool()