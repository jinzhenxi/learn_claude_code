"""错误恢复：三类 API 故障（截断 / 上下文超限 / 临时故障）的恢复策略。"""

from .backoff import retry_delay
from .controller import ErrorRecovery, RecoveryAction
from .errors import (
    MaxRetriesExceededError,
    PromptTooLongError,
    TransientAPIError,
)

__all__ = [
    "ErrorRecovery",
    "RecoveryAction",
    "retry_delay",
    "PromptTooLongError",
    "TransientAPIError",
    "MaxRetriesExceededError",
]
