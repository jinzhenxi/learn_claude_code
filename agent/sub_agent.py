"""子 Agent：受限工具、全新 messages、轮数上限，只回最终结论。"""

from typing import Any

from .base_agent import BaseAgent
from prompt import PromptManager, build_context


class SubAgent(BaseAgent):
    # 安全上限：连续工具调用不超过该轮数，防止子任务失控
    MAX_ROUNDS = 30

    def __init__(self, llm: Any, registry: Any, hooks: Any,
                 skills: Any = None, compactor: Any = None,
                 fallback_model_id: str | None = None) -> None:
        super().__init__(llm, registry, hooks, compactor, fallback_model_id)
        self.skills = skills
        # task10：system prompt 分段组装 + 缓存
        self._prompt = PromptManager()

    @property
    def system_prompt(self) -> str:
        context = build_context("sub", self.registry, self.skills, None)
        return self._prompt.get_system_prompt(context)

    @property
    def max_rounds(self) -> int:
        return self.MAX_ROUNDS

    @property
    def fire_stop(self) -> bool:
        # Stop 汇总是主 REPL 的语义，子 Agent 不触发
        return False

    def execute(self, description: str) -> str:
        """spawn 入口：全新 messages[] 跑自己的循环，结束只回最终文本。"""
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": description}
        ]
        self.run(messages)
        return self.extract_text(messages[-1]["content"])
