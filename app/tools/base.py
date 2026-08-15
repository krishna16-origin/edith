from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ToolCategory(str, Enum):
    WEB = "web"
    BROWSER = "browser"
    PHONE = "phone"
    EMAIL = "email"
    CALENDAR = "calendar"
    PAYMENT = "payment"
    MEMORY = "memory"
    SYSTEM = "system"


class ApprovalTier(str, Enum):
    TIER_1_READONLY = "tier_1_readonly"
    TIER_2_REVERSIBLE = "tier_2_reversible"
    TIER_3_IRREVERSIBLE = "tier_3_irreversible"


class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    category: ToolCategory
    approval_tier: ApprovalTier
    parameters: List[ToolParameter]
    returns: Dict[str, Any]
    examples: List[Dict[str, Any]] = []


class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class BaseTool(ABC):
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass
    
    def validate_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        required_params = [p.name for p in self.definition.parameters if p.required]
        for param in required_params:
            if param not in args:
                raise ValueError(f"Missing required parameter: {param}")
        return args


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        self._tools[tool.definition.name] = tool
    
    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)
    
    def list_tools(self) -> List[ToolDefinition]:
        return [tool.definition for tool in self._tools.values()]
    
    def get_by_category(self, category: ToolCategory) -> List[ToolDefinition]:
        return [t.definition for t in self._tools.values() if t.definition.category == category]
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{name}' not found")
        try:
            validated = tool.validate_args(kwargs)
            return await tool.execute(**validated)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


tool_registry = ToolRegistry()