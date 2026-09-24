"""客户端层：ClaudeClient 封装模型调用，核心方法 agent_loop。"""

import os
from typing import Any

from anthropic import Anthropic

from tools import ToolRegistry


class ClaudeClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        registry: ToolRegistry,
        max_tokens: int = 8000,
    ) -> None:
        # 显式传参，避免 ANTHROPIC_AUTH_TOKEN 等环境变量干扰
        self.client = Anthropic(base_url=base_url, api_key=api_key)
        self.model_id = model_id
        self.registry = registry
        self.max_tokens = max_tokens
        self.system = (
            f"You are a coding agent at {os.getcwd()}. "
            "Use bash to solve tasks. Act, don't explain."
        )

    def agent_loop(self, messages: list[dict[str, Any]]) -> None:
        """循环：请求模型 -> 执行工具 -> 回填结果，直到模型不再调工具。"""
        while True:
            response = self.client.messages.create(
                model=self.model_id,
                system=self.system,
                messages=messages,
                tools=self.registry.definitions(),
                max_tokens=self.max_tokens,
            )

            messages.append({"role": "assistant", "content": response.content})

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            # 没有工具调用即为本轮最终答复，结束循环
            if not tool_calls:
                return

            results = []
            for block in tool_calls:
                tool = self.registry.get(block.name)
                print(f"\033[33m{tool.preview(block.input)}\033[0m")
                output = tool.execute(**block.input)
                print(output[:200])
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })

            messages.append({"role": "user", "content": results})
