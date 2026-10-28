"""Task System 的工具适配层：5 个动作各一个 BaseTool，经注册表分发。

工具名用 task_* 前缀，与既有的 task（子 Agent spawner）区分。
工具不持有状态，全部代理给共享的 TaskManager（.tasks/ 落盘）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tools.base_tool import BaseTool

if TYPE_CHECKING:
    from .taskManager import TaskManager


class CreateTaskTool(BaseTool):
    name = "task_create"
    description = (
        "Create a persistent task with optional blockedBy dependency task IDs. "
        "Tasks form a DAG; a blocked task cannot be claimed until all "
        "dependencies are completed. Returns the new task ID."
    )

    def __init__(self, system: "TaskManager") -> None:
        self.system = system

    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "blockedBy": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["subject"],
        }

    def execute(self, subject: str, description: str = "",
                blockedBy: list[str] | None = None) -> str:
        task = self.system.create_task(subject, description, blockedBy)
        return f"Created {task.id}: {task.subject}"

    def preview(self, tool_input) -> str:
        return f"task_create: {str(tool_input.get('subject', ''))[:60]}"


class ListTasksTool(BaseTool):
    name = "task_list"
    description = "List all persistent tasks with status, owner, and dependencies."

    def __init__(self, system: "TaskManager") -> None:
        self.system = system

    def input_schema(self):
        return {"type": "object", "properties": {}}

    def execute(self) -> str:
        return self.system.list_tasks()

    def preview(self, tool_input) -> str:
        return "task_list"


class GetTaskTool(BaseTool):
    name = "task_get"
    description = "Get full JSON detail of one task (description, dependencies)."

    def __init__(self, system: "TaskManager") -> None:
        self.system = system

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        }

    def execute(self, task_id: str) -> str:
        return self.system.get_task(task_id)

    def preview(self, tool_input) -> str:
        return f"task_get {tool_input.get('task_id', '')}"


class ClaimTaskTool(BaseTool):
    name = "task_claim"
    description = (
        "Claim a pending task (pending -> in_progress) and set owner. "
        "Fails if the task is already claimed/owned or blocked by unfinished tasks."
    )

    def __init__(self, system: "TaskManager") -> None:
        self.system = system

    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "owner": {"type": "string"},
            },
            "required": ["task_id"],
        }

    def execute(self, task_id: str, owner: str = "agent") -> str:
        return self.system.claim_task(task_id, owner)

    def preview(self, tool_input) -> str:
        return f"task_claim {tool_input.get('task_id', '')}"


class CompleteTaskTool(BaseTool):
    name = "task_complete"
    description = (
        "Complete an in_progress task (in_progress -> completed) and list any "
        "downstream tasks it unblocks."
    )

    def __init__(self, system: "TaskManager") -> None:
        self.system = system

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        }

    def execute(self, task_id: str) -> str:
        return self.system.complete_task(task_id)

    def preview(self, tool_input) -> str:
        return f"task_complete {tool_input.get('task_id', '')}"


def build_task_tools(system: "TaskManager") -> list[BaseTool]:
    return [
        CreateTaskTool(system),
        ListTasksTool(system),
        GetTaskTool(system),
        ClaimTaskTool(system),
        CompleteTaskTool(system),
    ]
