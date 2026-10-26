"""指数退避 + 抖动：429 限流 / 529 过载的临时故障重试。"""

from __future__ import annotations

import random

# 第 attempt 次等待：0.5s, 1s, 2s, 4s... 封顶 32s；叠加最多 25% 随机抖动
BASE_MS = 500
CAP_MS = 32_000
JITTER_RATIO = 0.25


def retry_delay(attempt: int, retry_after: float | None = None) -> float:
    """attempt 从 0 开始。服务端给了 Retry-After 则优先采用。"""
    if retry_after is not None:
        return float(retry_after)
    base = min(BASE_MS * (2 ** attempt), CAP_MS) / 1000
    return base + random.uniform(0, base * JITTER_RATIO)
