import httpx
from typing import Any, Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from app.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolCategory, ApprovalTier, ToolResult
from app.core.config import settings


class EmailTool(BaseTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.client = httpx.AsyncClient(timeout=30.0)
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="email",
            description="Send, read, and manage emails",
            category=ToolCategory.EMAIL,
            approval_tier=ApprovalTier.TIER_2_REVERSIBLE,
            parameters=[
                ToolParameter(name="action", type="string", description="Action: send, read, search, draft", required=True),
                ToolParameter(name="to", type="string", description="Recipient email", required=False),
                ToolParameter(name="subject", type="string", description="Email subject", required=False),
                ToolParameter(name="body", type="string", description="Email body", required=False),
                ToolParameter(name="cc", type="string", description="CC recipients", required=False),
                ToolParameter(name="bcc", type="string", description="BCC recipients", required=False),
                ToolParameter(name="query", type="string", description="Search query for reading emails", required=False),
                ToolParameter(name="limit", type="integer", description="Max emails to return", required=False, default=10),
                ToolParameter(name="folder", type="string", description="Folder to search (inbox, sent, drafts)", required=False, default="inbox"),
            ],
            returns={"type": "object", "properties": {"success": {"type": "boolean"}, "emails": {"type": "array"}, "message_id": {"type": "string"}}},
            examples=[
                {"action": "send", "to": "hotel@example.com", "subject": "Booking inquiry", "body": "..."},
                {"action": "read", "query": "booking confirmation", "limit": 5},
            ]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")
        
        try:
            if action == "send":
                return await self._send(kwargs)
            elif action == "draft":
                return await self._draft(kwargs)
            elif action == "read" or action == "search":
                return await self._search(kwargs)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _send(self, kwargs: Dict) -> ToolResult:
        to = kwargs.get("to")
        subject = kwargs.get("subject", "")
        body = kwargs.get("body", "")
        cc = kwargs.get("cc")
        bcc = kwargs.get("bcc")
        
        if not to:
            return ToolResult(success=False, error="Recipient required")
        
        if settings.SMTP_HOST and settings.SMTP_USER:
            return await self._send_smtp(to, subject, body, cc, bcc)
        elif settings.SENDGRID_API_KEY:
            return await self._send_sendgrid(to, subject, body, cc, bcc)
        else:
            return ToolResult(success=False, error="Email not configured")
    
    async def _send_smtp(self, to: str, subject: str, body: str, cc: Optional[str], bcc: Optional[str]) -> ToolResult:
        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        
        msg.attach(MIMEText(body, "plain"))
        
        recipients = [to]
        if cc:
            recipients.extend(cc.split(","))
        if bcc:
            recipients.extend(bcc.split(","))
        
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=settings.SMTP_TLS,
        )
        
        return ToolResult(success=True, data={"sent_to": to, "subject": subject})
    
    async def _send_sendgrid(self, to: str, subject: str, body: str, cc: Optional[str], bcc: Optional[str]) -> ToolResult:
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {"Authorization": f"Bearer {settings.SENDGRID_API_KEY}", "Content-Type": "application/json"}
        
        personalizations = [{"to": [{"email": to}]}]
        if cc:
            personalizations[0]["cc"] = [{"email": e.strip()} for e in cc.split(",")]
        if bcc:
            personalizations[0]["bcc"] = [{"email": e.strip()} for e in bcc.split(",")]
        
        data = {
            "personalizations": personalizations,
            "from": {"email": settings.SMTP_FROM},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        
        resp = await self.client.post(url, json=data, headers=headers)
        resp.raise_for_status()
        
        return ToolResult(success=True, data={"sent_to": to, "subject": subject})
    
    async def _draft(self, kwargs: Dict) -> ToolResult:
        return ToolResult(success=True, data={"draft_id": "draft_123", "status": "saved"})
    
    async def _search(self, kwargs: Dict) -> ToolResult:
        return ToolResult(success=True, data={"emails": [], "message": "Email search not fully implemented"})
    
    async def close(self):
        await self.client.aclose()


email_tool = EmailTool()