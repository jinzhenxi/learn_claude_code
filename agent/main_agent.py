"""主 Agent：完整工具集、不限轮数、持有 TodoManager。"""

import os
from typing import TYPE_CHECKING, Any

from .base_agent import BaseAgent

if TYPE_CHECKING:
    from todos import TodoManager


class MainAgent(BaseAgent):
    def __init__(
        self,
        llm: Any,
        registry: Any,
        hooks: Any,
        todos: "TodoManager",
    ) -> None:
        super().__init__(llm, registry, hooks)
        self.todos = todos

    @property
    def system_prompt(self) -> str:
        return (
            f"You are a coding agent at {os.getcwd()}. "
            "Use tools to solve tasks. Act, don't explain. "
            "Before starting any multi-step task, use todo_write to plan your "
            "steps, and update status as you go. "
            "Delegate self-contained subtasks to the task tool; it returns "
            "only the subagent's final conclusion. "
            "Every tool call passes through hooks: if a tool returns an "
            "error, fix the arguments and retry; if a hook blocks the call, "
            "do not repeat the action, choose another approach."
        )

    def observe_round(self) -> list[dict[str, Any]]:
        # 闲置满 3 轮时由 TodoManager 决定追加提醒
        reminder = self.todos.advance_round()
        return [{"type": "text", "text": reminder}] if reminder else []
