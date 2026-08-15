import asyncio
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from app.tools.base import BaseTool, ToolDefinition, ToolParameter, ToolCategory, ApprovalTier, ToolResult
from app.core.config import settings


class BrowserTool(BaseTool):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._playwright = None
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="browser",
            description="Control a web browser to navigate, click, type, and extract data from websites",
            category=ToolCategory.BROWSER,
            approval_tier=ApprovalTier.TIER_1_READONLY,
            parameters=[
                ToolParameter(name="action", type="string", description="Action to perform: navigate, click, type, extract, screenshot, wait", required=True),
                ToolParameter(name="url", type="string", description="URL to navigate to (for navigate action)", required=False),
                ToolParameter(name="selector", type="string", description="CSS selector for element (for click, type, extract)", required=False),
                ToolParameter(name="text", type="string", description="Text to type (for type action)", required=False),
                ToolParameter(name="attribute", type="string", description="Attribute to extract (for extract action)", required=False, default="text"),
                ToolParameter(name="wait_for", type="string", description="Selector to wait for before proceeding", required=False),
                ToolParameter(name="timeout", type="integer", description="Timeout in milliseconds", required=False, default=30000),
            ],
            returns={"type": "object", "properties": {"success": {"type": "boolean"}, "data": {"type": "object"}, "error": {"type": "string"}}},
            examples=[
                {"action": "navigate", "url": "https://example.com"},
                {"action": "click", "selector": "button.submit"},
                {"action": "type", "selector": "input#search", "text": "query"},
                {"action": "extract", "selector": ".price", "attribute": "text"},
            ]
        )
    
    async def _ensure_browser(self):
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=settings.BROWSER_HEADLESS,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            self._page = await self._context.new_page()
            self._page.set_default_timeout(settings.BROWSER_TIMEOUT)
    
    async def execute(self, **kwargs) -> ToolResult:
        await self._ensure_browser()
        
        action = kwargs.get("action")
        try:
            if action == "navigate":
                return await self._navigate(kwargs)
            elif action == "click":
                return await self._click(kwargs)
            elif action == "type":
                return await self._type(kwargs)
            elif action == "extract":
                return await self._extract(kwargs)
            elif action == "screenshot":
                return await self._screenshot(kwargs)
            elif action == "wait":
                return await self._wait(kwargs)
            elif action == "eval":
                return await self._eval(kwargs)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _navigate(self, kwargs: Dict) -> ToolResult:
        url = kwargs.get("url")
        wait_for = kwargs.get("wait_for")
        timeout = kwargs.get("timeout", settings.BROWSER_TIMEOUT)
        
        if not url:
            return ToolResult(success=False, error="URL required for navigate")
        
        await self._page.goto(url, wait_until="networkidle", timeout=timeout)
        if wait_for:
            await self._page.wait_for_selector(wait_for, timeout=timeout)
        
        return ToolResult(success=True, data={"url": self._page.url, "title": await self._page.title()})
    
    async def _click(self, kwargs: Dict) -> ToolResult:
        selector = kwargs.get("selector")
        if not selector:
            return ToolResult(success=False, error="Selector required for click")
        
        await self._page.click(selector)
        return ToolResult(success=True, data={"clicked": selector})
    
    async def _type(self, kwargs: Dict) -> ToolResult:
        selector = kwargs.get("selector")
        text = kwargs.get("text")
        if not selector or text is None:
            return ToolResult(success=False, error="Selector and text required for type")
        
        await self._page.fill(selector, text)
        return ToolResult(success=True, data={"typed": text, "into": selector})
    
    async def _extract(self, kwargs: Dict) -> ToolResult:
        selector = kwargs.get("selector")
        attribute = kwargs.get("attribute", "text")
        if not selector:
            return ToolResult(success=False, error="Selector required for extract")
        
        elements = await self._page.query_selector_all(selector)
        results = []
        for el in elements:
            if attribute == "text":
                val = await el.inner_text()
            elif attribute == "html":
                val = await el.inner_html()
            else:
                val = await el.get_attribute(attribute)
            results.append(val)
        
        return ToolResult(success=True, data={"results": results, "count": len(results)})
    
    async def _screenshot(self, kwargs: Dict) -> ToolResult:
        path = kwargs.get("path", f"screenshot_{asyncio.get_event_loop().time()}.png")
        full_page = kwargs.get("full_page", True)
        await self._page.screenshot(path=path, full_page=full_page)
        return ToolResult(success=True, data={"path": path})
    
    async def _wait(self, kwargs: Dict) -> ToolResult:
        selector = kwargs.get("selector")
        timeout = kwargs.get("timeout", settings.BROWSER_TIMEOUT)
        if selector:
            await self._page.wait_for_selector(selector, timeout=timeout)
        else:
            await asyncio.sleep(kwargs.get("seconds", 1))
        return ToolResult(success=True)
    
    async def _eval(self, kwargs: Dict) -> ToolResult:
        script = kwargs.get("script")
        if not script:
            return ToolResult(success=False, error="Script required for eval")
        result = await self._page.evaluate(script)
        return ToolResult(success=True, data={"result": result})
    
    async def close(self):
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


browser_tool = BrowserTool()