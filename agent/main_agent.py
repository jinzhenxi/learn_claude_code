"""主 Agent：完整工具集、不限轮数、持有 TodoManager。"""

from typing import TYPE_CHECKING, Any

from .base_agent import BaseAgent
from prompt import PromptManager, build_context

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
        # task10：system prompt 分段组装 + 缓存，循环零感知
        self._prompt = PromptManager()

    @property
    def system_prompt(self) -> str:
        context = build_context("main", self.registry, self.skills, self.memory)
        return self._prompt.get_system_prompt(context)

    def observe_round(self) -> list[dict[str, Any]]:
        # 闲置满 3 轮时由 TodoManager 决定追加提醒
        reminder = self.todos.advance_round()
        return [{"type": "text", "text": reminder}] if reminder else []
