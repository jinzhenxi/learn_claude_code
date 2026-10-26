"""客户端层：ClaudeClient 是对 Anthropic Messages API 的薄封装。

不管循环、不认识工具，只负责一次模型调用；主 Agent 与子 Agent 共用它，
所以两边的模型、鉴权和端点天然一致。SDK 错误在这里归一化：
413/prompt 过长 → PromptTooLongError；429 → 限流；529 → 过载
（后两者为 TransientAPIError），交给 recovery 包决定恢复动作。
"""

from __future__ import annotations

from typing import Any

from anthropic import Anthropic, APIStatusError, RateLimitError

from recovery.errors import PromptTooLongError, TransientAPIError

__all__ = ["ClaudeClient", "PromptTooLongError", "TransientAPIError"]


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

    def create(
        self,
        system: str,
        messages: list,
        tools: list,
        max_tokens: int | None = None,
        model_id: str | None = None,
    ) -> object:
        """max_tokens / model_id 可逐请求覆盖（供错误恢复升级预算、切备用模型）。"""
        try:
            return self.client.messages.create(
                model=model_id or self.model_id,
                system=system,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens or self.max_tokens,
            )
        except RateLimitError as e:
            raise TransientAPIError(
                str(e), overloaded=False, retry_after=self._retry_after(e)
            ) from e
        except APIStatusError as e:
            if e.status_code == 413 or "prompt is too long" in str(e).lower():
                raise PromptTooLongError(str(e)) from e
            if e.status_code == 529:
                raise TransientAPIError(
                    str(e), overloaded=True, retry_after=self._retry_after(e)
                ) from e
            raise

    @staticmethod
    def _retry_after(error: APIStatusError) -> float | None:
        """解析服务端 Retry-After（秒），缺失或非法返回 None。"""
        try:
            raw: Any = error.response.headers.get("retry-after")
            return float(raw) if raw is not None else None
        except (AttributeError, ValueError):
            return None
