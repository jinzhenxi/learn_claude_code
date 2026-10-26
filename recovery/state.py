"""错误恢复的运行时状态：一次 agent run 内有效，run 结束即丢弃。"""

from __future__ import annotations

from dataclasses import dataclass

# 输出预算
DEFAULT_MAX_TOKENS = 8_000
ESCALATED_MAX_TOKENS = 64_000      # 首次截断：8K → 64K
MAX_CONTINUATIONS = 3              # 64K 仍截断：最多续写 3 次

# 临时故障
MAX_TRANSIENT_RETRIES = 10         # 429/529 最多重试 10 次
OVERLOADED_FALLBACK_THRESHOLD = 3  # 连续 3 次 529 切备用模型

CONTINUATION_PROMPT = (
    "Output token limit hit. Resume directly — "
    "no apology, no recap. Pick up mid-thought."
)


@dataclass
class RecoveryState:
    max_tokens: int = DEFAULT_MAX_TOKENS
    model_id: str | None = None  # None 表示用 client 默认模型

    # 截断恢复
    has_escalated: bool = False      # 是否已从 8K 升到 64K
    continuation_count: int = 0     # 64K 后续写次数

    # 上下文超限恢复
    reactive_attempted: bool = False  # reactive compact 是否已经跑过一次

    # 临时故障恢复
    transient_attempt: int = 0          # 已退避重试次数
    consecutive_overloaded: int = 0     # 连续 529 次数
