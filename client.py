"""客户端层：ClaudeClient 是对 Anthropic Messages API 的薄封装。

不管循环、不认识工具，只负责一次模型调用；主 Agent 与子 Agent 共用它，
所以两边的模型、鉴权和端点天然一致。
"""

from anthropic import Anthropic


class ClaudeClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        max_tokens: int = 8000,
    ) -> None:
        # 显式传参，避免 ANTHROPIC_AUTH_TOKEN 等环境变量干扰
        self.client = Anthropic(base_url=base_url, api_key=api_key)
        self.model_id = model_id
        self.max_tokens = max_tokens

    def create(self, system: str, messages: list, tools: list) -> object:
        return self.client.messages.create(
            model=self.model_id,
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=self.max_tokens,
        )
