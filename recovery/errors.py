"""错误恢复层的异常归一。

client 把 SDK 的各类状态错误翻译成这里的语义异常，agent loop 只需按
"截断 / 上下文超限 / 临时故障" 三类决策，不耦合具体 SDK。
"""

from __future__ import annotations

from typing import Any


class PromptTooLongError(Exception):
    """上下文超过模型窗口（413 / prompt_too_long）。"""


class TransientAPIError(Exception):
    """临时故障：429 限流或 529 过载，可退避后重试。"""

    def __init__(
        self,
        message: str,
        *,
        overloaded: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.overloaded = overloaded
        # 服务端 Retry-After（秒）；存在时退避直接采用
        self.retry_after = retry_after


class MaxRetriesExceededError(Exception):
    """临时故障重试次数耗尽。"""
