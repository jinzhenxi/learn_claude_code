"""子 Agent：受限工具、全新 messages、轮数上限，只回最终结论。"""

import os
from typing import Any

from .base_agent import BaseAgent


class SubAgent(BaseAgent):
    # 安全上限：连续工具调用不超过该轮数，防止子任务失控
    MAX_ROUNDS = 30

    @property
    def system_prompt(self) -> str:
        return (
            f"You are a subagent at {os.getcwd()}, spawned to complete one "
            "delegated subtask. Work autonomously with the available tools; "
            "file changes persist in the shared workspace. When finished, "
            "reply with only the final conclusion to return to the parent."
        )

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
