"""主 Agent：完整工具集、不限轮数、持有 TodoManager。"""

import os
from typing import TYPE_CHECKING, Any

from .base_agent import BaseAgent

if TYPE_CHECKING:
    from todos import TodoManager
    from memory import MemoryManager


class MainAgent(BaseAgent):
    def __init__(
        self,
        llm: Any,
        registry: Any,
        hooks: Any,
        todos: "TodoManager",
        skills: Any = None,
        compactor: Any = None,
        memory: "MemoryManager | None" = None,
    ) -> None:
        super().__init__(llm, registry, hooks, compactor)
        self.todos = todos
        self.skills = skills
        self.memory = memory

    @property
    def system_prompt(self) -> str:
        prompt = (
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
        catalog = self.skills.catalog() if self.skills else ""
        parts = [prompt]
        if catalog:
            parts.append(catalog)
        # task09：记忆索引常驻 SYSTEM（可被 prompt cache 缓存），正文按需注入 user turn
        if self.memory is not None:
            from memory import system_index_text
            idx = system_index_text(self.memory)
            if idx:
                parts.append(idx)
        return "\n\n".join(parts)

    def observe_round(self) -> list[dict[str, Any]]:
        # 闲置满 3 轮时由 TodoManager 决定追加提醒
        reminder = self.todos.advance_round()
        return [{"type": "text", "text": reminder}] if reminder else []
