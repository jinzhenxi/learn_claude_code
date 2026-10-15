"""compact 工具：模型主动触发全量上下文压缩。

工具本身不直接改 messages（它拿不到），而是通过 ToolResult.directive
下发一条 CompactDirective，由 Agent 循环执行压缩并结束当前 turn。
"""

from typing import TYPE_CHECKING

from compaction import CompactDirective

from .base_tool import BaseTool, ToolResult

if TYPE_CHECKING:
    from compaction import ContextCompactor


class CompactTool(BaseTool):
    name = "compact"
    description = (
        "Summarize and compact the conversation history when context is "
        "getting long. Call proactively before hitting context limits; the "
        "full transcript is saved before compaction."
    )

    def __init__(self, compactor: "ContextCompactor") -> None:
        self.compactor = compactor

    def input_schema(self):
        # 无参：上下文由 Agent 持有，模型无需传入
        return {"type": "object", "properties": {}}

    def execute(self) -> ToolResult:
        return ToolResult(
            content="[Compacted. History summarized.]",
            directive=CompactDirective(self.compactor),
        )

    def preview(self, tool_input) -> str:
        return "compact (summarize history)"
