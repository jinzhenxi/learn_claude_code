"""todo_write 工具：整体替换模型维护的进度列表，状态归 TodoManager。"""

from typing import TYPE_CHECKING, Any

from .base_tool import BaseTool

if TYPE_CHECKING:
    from todos import TodoManager


class TodoWriteTool(BaseTool):
    name = "todo_write"
    description = (
        "Create or replace the task todo list. Call before multi-step work "
        "and update status as you progress; the whole list is replaced."
    )

    def __init__(self, manager: "TodoManager") -> None:
        # 不持有状态本身，只代理给共享的 TodoManager
        self.manager = manager

    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "maxItems": 20,
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["content"],
                    },
                }
            },
            "required": ["todos"],
        }

    def execute(self, todos: Any) -> str:
        return self.manager.update(todos)

    def preview(self, tool_input) -> str:
        return f"todo_write ({len(tool_input.get('todos', []))} items)"
