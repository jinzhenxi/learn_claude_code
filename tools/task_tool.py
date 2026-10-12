"""task 工具：spawn 一个子 Agent，只回最终结论。"""

from typing import TYPE_CHECKING, Any

from agent import SubAgent

from .base_tool import BaseTool

if TYPE_CHECKING:
    from .tool_manager import ToolManager


class TaskTool(BaseTool):
    name = "task"
    description = (
        "Launch a subagent to handle a complex, self-contained subtask. The "
        "subagent runs in an isolated conversation and returns only its "
        "final conclusion; file changes persist in the workspace."
    )

    def __init__(self, llm: Any, hooks: Any, sub_manager: "ToolManager",
                 skills: Any = None) -> None:
        self.llm = llm
        self.hooks = hooks
        # 受限管理器：只有基础五工具，天然无法再调用 task
        self.sub_manager = sub_manager
        self.skills = skills

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"description": {"type": "string"}},
            "required": ["description"],
        }

    def execute(self, description: str) -> str:
        # 每次调用 spawn 新的 SubAgent：messages 隔离，hooks 仍是同一份
        sub = SubAgent(self.llm, self.sub_manager, self.hooks, self.skills)
        return sub.execute(description)

    def preview(self, tool_input) -> str:
        return f"task: {str(tool_input.get('description', ''))[:60]}"
