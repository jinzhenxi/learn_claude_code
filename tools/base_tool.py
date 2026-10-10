"""工具基类：所有工具继承 BaseTool，只需实现 schema 与执行逻辑。

run() 是模板方法，也是唯一的异常收口点——任何工具失败都归一成
ToolResult，绝不把异常抛给 Agent。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """一次工具调用的归一化结果：永不以异常形式出现。"""

    content: str
    is_error: bool = False


class BaseTool(ABC):
    """统一工具接口；新增工具只需继承并注册进 ToolManager，Agent 无需改动。"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """工具入参的 JSON Schema。"""

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """成功路径返回文本；失败直接 raise，无需自行 try/except。"""

    def run(self, **kwargs: Any) -> ToolResult:
        try:
            return ToolResult(content=self.execute(**kwargs))
        except Exception as e:
            return ToolResult(
                content=f"Error: {type(e).__name__}: {e}",
                is_error=True,
            )

    def definition(self) -> dict[str, Any]:
        # 给 LLM 看的静态元信息
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }

    def preview(self, tool_input: dict[str, Any]) -> str:
        """终端中展示本次调用的摘要，默认打印原始入参。"""
        return f"{self.name} {tool_input}"
