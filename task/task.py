"""Task 结构体与状态机常量。

每个任务是 .tasks/{id}.json 一个文件；ID 为 task_{时间戳}_{4位hex}。
状态机：pending ──claim──▶ in_progress ──complete──▶ completed
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

PENDING = "pending"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
VALID_STATUSES = frozenset({PENDING, IN_PROGRESS, COMPLETED})


@dataclass
class Task:
    id: str
    subject: str
    description: str = ""
    status: str = PENDING
    owner: str | None = None
    blockedBy: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        # 只取已知字段，忽略文件里可能多出的键，保证向前兼容
        return cls(
            id=data["id"],
            subject=data.get("subject", ""),
            description=data.get("description", ""),
            status=data.get("status", PENDING),
            owner=data.get("owner"),
            blockedBy=list(data.get("blockedBy", [])),
        )
