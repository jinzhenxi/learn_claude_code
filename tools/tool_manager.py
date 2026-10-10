"""工具管理器：按名字注册/查找工具，执行分发完全替代 if-else。"""

from typing import Any

from .base_tool import BaseTool


class ToolManager:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> "ToolManager":
        if not tool.name:
            raise ValueError("tool.name must not be empty")
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Unknown tool: {name}") from None

    def definitions(self) -> list[dict[str, Any]]:
        # 导出给 LLM 的工具清单
        return [tool.definition() for tool in self._tools.values()]
