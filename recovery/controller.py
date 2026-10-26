"""错误恢复控制器：三类故障的决策全部收敛在这里，agent loop 只转发信号。

  handle_truncation      输出截断：先升 8K→64K 原请求重试，再续写（≤3 次）
  handle_prompt_too_long 上下文超限：reactive compact 一次；仍超限则放弃
  handle_transient       429/529：指数退避抖动，≤10 次；连续 3 次 529 切备用模型
"""

from __future__ import annotations

import enum
import time
from typing import Any, Callable

from .backoff import retry_delay
from .errors import MaxRetriesExceededError, TransientAPIError
from .state import (
    CONTINUATION_PROMPT,
    ESCALATED_MAX_TOKENS,
    MAX_CONTINUATIONS,
    MAX_TRANSIENT_RETRIES,
    OVERLOADED_FALLBACK_THRESHOLD,
    RecoveryState,
)


class RecoveryAction(enum.Enum):
    RETRY = "retry"   # 已调整请求参数或 messages，回到循环顶部重试
    ABORT = "abort"   # 恢复手段耗尽，结束本次 run


class ErrorRecovery:
    """一次 agent run 持有一个实例；sleeper 可注入以便测试。"""

    def __init__(
        self,
        compactor: Any = None,
        fallback_model_id: str | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.compactor = compactor
        self.fallback_model_id = fallback_model_id
        self._sleep = sleeper
        self.state = RecoveryState()

    @property
    def max_tokens(self) -> int:
        return self.state.max_tokens

    @property
    def model_id(self) -> str | None:
        return self.state.model_id

    # -- (1) 输出截断 --

    def handle_truncation(
        self, messages: list[dict[str, Any]], content: Any
    ) -> RecoveryAction:
        s = self.state
        if not s.has_escalated:
            # 第一次：不追加截断输出，同一请求用 8 倍预算重发
            s.has_escalated = True
            s.max_tokens = ESCALATED_MAX_TOKENS
            return RecoveryAction.RETRY

        # 64K 仍截断：保留半截输出并注入续写提示
        messages.append({"role": "assistant", "content": content})
        if s.continuation_count < MAX_CONTINUATIONS:
            messages.append({"role": "user", "content": CONTINUATION_PROMPT})
            s.continuation_count += 1
            return RecoveryAction.RETRY
        return RecoveryAction.ABORT

    # -- (2) 上下文超限 --

    def handle_prompt_too_long(
        self, messages: list[dict[str, Any]]
    ) -> RecoveryAction:
        s = self.state
        if s.reactive_attempted or self.compactor is None:
            # 已经激进压缩过一次仍超限：再压不会更小，放弃
            return RecoveryAction.ABORT
        messages[:] = self.compactor.reactive_compact(messages)
        s.reactive_attempted = True
        return RecoveryAction.RETRY

    # -- (3) 临时故障：429 / 529 --

    def handle_transient(self, error: TransientAPIError) -> None:
        """退避等待后返回（调用方 continue 重试）；超 10 次抛异常。"""
        s = self.state
        if s.transient_attempt >= MAX_TRANSIENT_RETRIES:
            raise MaxRetriesExceededError(
                f"transient API errors persisted after "
                f"{MAX_TRANSIENT_RETRIES} retries: {error}"
            )

        if error.overloaded:
            s.consecutive_overloaded += 1
            if (
                s.consecutive_overloaded >= OVERLOADED_FALLBACK_THRESHOLD
                and self.fallback_model_id
                and s.model_id != self.fallback_model_id
            ):
                s.model_id = self.fallback_model_id
        else:
            # 429 不是过载，连续 529 计数中断
            s.consecutive_overloaded = 0

        delay = retry_delay(s.transient_attempt, error.retry_after)
        s.transient_attempt += 1
        self._sleep(delay)

    def note_success(self) -> None:
        """一次调用成功：临时故障计数归零，截断/压缩类状态保持不变。"""
        self.state.transient_attempt = 0
        self.state.consecutive_overloaded = 0
