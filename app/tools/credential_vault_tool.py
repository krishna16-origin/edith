import httpx
from typing import Any, Dict, List, Optional
from app.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolCategory, ApprovalTier, ToolResult
from app.core.config import settings


class CredentialVaultTool(BaseTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.client = httpx.AsyncClient(timeout=30.0)
        self._access_token = None
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="credential_vault",
            description="Retrieve credentials from user's password manager (Bitwarden/1Password)",
            category=ToolCategory.SYSTEM,
            approval_tier=ApprovalTier.TIER_1_READONLY,
            parameters=[
                ToolParameter(name="action", type="string", description="Action: get, list", required=True),
                ToolParameter(name="item_name", type="string", description="Name of the credential item", required=False),
                ToolParameter(name="item_id", type="string", description="ID of the credential item", required=False),
                ToolParameter(name="field", type="string", description="Specific field to retrieve (username, password, totp, etc.)", required=False),
            ],
            returns={"type": "object", "properties": {"credential": {"type": "object"}, "items": {"type": "array"}}},
            examples=[
                {"action": "get", "item_name": "Gmail", "field": "password"},
                {"action": "list"},
            ]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action")
        
        if not settings.BITWARDEN_CLIENT_ID:
            return ToolResult(success=False, error="Bitwarden not configured")
        
        try:
            if action == "get":
                return await self._get(kwargs)
            elif action == "list":
                return await self._list(kwargs)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        
        url = "https://identity.bitwarden.com/connect/token"
        data = {
            "grant_type": "client_credentials",
            "scope": "api.vault",
            "client_id": settings.BITWARDEN_CLIENT_ID,
            "client_secret": settings.BITWARDEN_CLIENT_SECRET,
        }
        
        resp = await self.client.post(url, data=data)
        resp.raise_for_status()
        token_data = resp.json()
        self._access_token = token_data["access_token"]
        return self._access_token
    
    async def _get(self, kwargs: Dict) -> ToolResult:
        item_name = kwargs.get("item_name")
        item_id = kwargs.get("item_id")
        field = kwargs.get("field")
        
        if not item_name and not item_id:
            return ToolResult(success=False, error="item_name or item_id required")
        
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        if item_id:
            url = f"https://api.bitwarden.com/public/items/{item_id}"
            resp = await self.client.get(url, headers=headers)
        else:
            url = "https://api.bitwarden.com/public/items"
            params = {"search": item_name}
            resp = await self.client.get(url, headers=headers, params=params)
            data = resp.json()
            items = data.get("data", [])
            if not items:
                return ToolResult(success=False, error="Item not found")
            item_id = items[0]["id"]
            resp = await self.client.get(f"https://api.bitwarden.com/public/items/{item_id}", headers=headers)
        
        resp.raise_for_status()
        item = resp.json()
        
        login = item.get("login", {})
        result = {
            "id": item["id"],
            "name": item["name"],
            "username": login.get("username"),
            "password": login.get("password"),
            "uris": login.get("uris", []),
        }
        
        if field and field in result:
            return ToolResult(success=True, data={"credential": {field: result[field]}})
        
        return ToolResult(success=True, data={"credential": result})
    
    async def _list(self, kwargs: Dict) -> ToolResult:
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        url = "https://api.bitwarden.com/public/items"
        resp = await self.client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        items = []
        for item in data.get("data", []):
            login = item.get("login", {})
            items.append({
                "id": item["id"],
                "name": item["name"],
                "username": login.get("username"),
                "uris": [u.get("uri") for u in login.get("uris", [])],
            })
        
        return ToolResult(success=True, data={"items": items})
    
    async def close(self):
        await self.client.aclose()


credential_vault_tool = CredentialVaultTool()