import httpx
from typing import Any, Dict, List, Optional
from app.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolCategory, ApprovalTier, ToolResult
from app.core.config import settings


class WebSearchTool(BaseTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.client = httpx.AsyncClient(timeout=30.0)
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="web_search",
            description="Search the web for information using a search API",
            category=ToolCategory.WEB,
            approval_tier=ApprovalTier.TIER_1_READONLY,
            parameters=[
                ToolParameter(name="query", type="string", description="Search query", required=True),
                ToolParameter(name="num_results", type="integer", description="Number of results to return", required=False, default=10),
                ToolParameter(name="recency_days", type="integer", description="Limit results to last N days", required=False),
                ToolParameter(name="site", type="string", description="Restrict search to specific site", required=False),
            ],
            returns={"type": "object", "properties": {"results": {"type": "array"}, "query": {"type": "string"}}},
            examples=[
                {"query": "best hotels in Goa", "num_results": 5},
                {"query": "flight prices NYC to London", "recency_days": 7},
            ]
        )
    
    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query")
        num_results = kwargs.get("num_results", 10)
        recency_days = kwargs.get("recency_days")
        site = kwargs.get("site")
        
        if not query:
            return ToolResult(success=False, error="Query required")
        
        search_query = query
        if site:
            search_query += f" site:{site}"
        
        try:
            if settings.GOOGLE_API_KEY:
                return await self._google_search(search_query, num_results, recency_days)
            else:
                return await self._duckduckgo_search(search_query, num_results)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _google_search(self, query: str, num_results: int, recency_days: Optional[int]) -> ToolResult:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": settings.GOOGLE_API_KEY,
            "cx": "custom_search_engine_id",
            "q": query,
            "num": min(num_results, 10),
        }
        if recency_days:
            params["dateRestrict"] = f"d{recency_days}"
        
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
            })
        
        return ToolResult(success=True, data={"results": results, "query": query})
    
    async def _duckduckgo_search(self, query: str, num_results: int) -> ToolResult:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", "Result"),
                "link": data.get("AbstractURL", ""),
                "snippet": data.get("Abstract", ""),
            })
        for topic in data.get("RelatedTopics", [])[:num_results-1]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:100],
                    "link": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                })
        
        return ToolResult(success=True, data={"results": results, "query": query})
    
    async def close(self):
        await self.client.aclose()


web_search_tool = WebSearchTool()