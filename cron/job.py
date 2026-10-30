"""CronJob 数据结构：五段式 cron + 触发消息 + 周期/持久标记。"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field


@dataclass
class CronJob:
    id: str
    cron: str           # "0 9 * * *" 五段式
    prompt: str         # 触发时注入给 Agent 的消息
    recurring: bool = True   # True=周期性，False=一次性
    durable: bool = True     # True=写磁盘，跨会话保留
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CronJob":
        return cls(
            id=data["id"],
            cron=data["cron"],
            prompt=data["prompt"],
            recurring=data.get("recurring", True),
            durable=data.get("durable", True),
            created_at=data.get("created_at", time.time()),
        )
