"""TaskManager：任务状态机与依赖（blockedBy）规则。

状态机：pending ──claim──▶ in_progress ──complete──▶ completed。
- can_start：blockedBy 全部 completed 才可开始；不存在的依赖视为 blocked。
- claim：仅 pending 且依赖就绪可认领，设置 owner，多 Agent 下靠锁防重复认领。
- complete：仅 in_progress 可完成，并报告因此解锁的下游任务。
"""

from __future__ import annotations

import json
import secrets
import time

from .task import COMPLETED, IN_PROGRESS, PENDING, Task
from .store import TaskStore


def new_task_id() -> str:
    return f"task_{int(time.time())}_{secrets.token_hex(2)}"


class TaskManager:
    def __init__(self, store: TaskStore | None = None) -> None:
        self.store = store or TaskStore()

    # -- 创建 --

    def create_task(
        self,
        subject: str,
        description: str = "",
        blocked_by: list[str] | None = None,
    ) -> Task:
        subject = str(subject).strip()
        if not subject:
            raise ValueError("subject must not be empty")
        task = Task(
            id=new_task_id(),
            subject=subject,
            description=str(description),
            status=PENDING,
            owner=None,
            blockedBy=list(blocked_by or []),
        )
        # 创建即落盘（锁内，避免与并发迁移交错）
        with self.store.locked():
            self.store.save(task)
        return task

    # -- 依赖检查 --

    def can_start(self, task_id: str) -> bool:
        """所有 blockedBy 均 completed 才可开始；缺失/非完成依赖均阻塞。"""
        task = self.store.load(task_id)
        for dep_id in task.blockedBy:
            if not self.store.exists(dep_id):
                return False  # 引用了不存在的 ID：按 blocked 处理，不崩溃
            if self.store.load(dep_id).status != COMPLETED:
                return False
        return True

    def _blocking_deps(self, task: Task) -> list[str]:
        """返回尚未满足的依赖 ID（含不存在的）。"""
        blocking = []
        for dep_id in task.blockedBy:
            if not self.store.exists(dep_id):
                blocking.append(dep_id)
            elif self.store.load(dep_id).status != COMPLETED:
                blocking.append(dep_id)
        return blocking

    # -- 状态迁移 --

    def claim_task(self, task_id: str, owner: str = "agent") -> str:
        with self.store.locked():
            task = self.store.load(task_id)
            if task.status != PENDING:
                return f"Task {task_id} is {task.status}, cannot claim"
            blocking = self._blocking_deps(task)
            if blocking:
                return f"Blocked by: {blocking}"
            task.owner = owner
            task.status = IN_PROGRESS
            self.store.save(task)
            return f"Claimed {task_id} ({task.subject})"

    def complete_task(self, task_id: str) -> str:
        with self.store.locked():
            task = self.store.load(task_id)
            if task.status != IN_PROGRESS:
                return f"Task {task_id} is {task.status}, cannot complete"
            task.status = COMPLETED
            self.store.save(task)

            # 扫描刚刚被解锁的下游：仍 pending、声明了依赖、且现在全部就绪
            unblocked = [
                t.subject
                for t in self.store.all()
                if t.status == PENDING and t.blockedBy and self._can_start_locked(t)
            ]

        msg = f"Completed {task_id} ({task.subject})"
        if unblocked:
            msg += f"\nUnblocked: {', '.join(unblocked)}"
        return msg

    def _can_start_locked(self, task: Task) -> bool:
        for dep_id in task.blockedBy:
            if not self.store.exists(dep_id):
                return False
            if self.store.load(dep_id).status != COMPLETED:
                return False
        return True

    # -- 查询 --

    def get_task(self, task_id: str) -> str:
        """完整 JSON（含 description / 依赖），供跨会话恢复时读取。"""
        return json.dumps(self.store.load(task_id).to_dict(),
                          ensure_ascii=False, indent=2)

    def list_tasks(self) -> str:
        """一行一个摘要：状态 / owner / subject / 依赖。"""
        tasks = self.store.all()
        if not tasks:
            return "No tasks."
        lines = []
        for t in tasks:
            owner = f" @{t.owner}" if t.owner else ""
            deps = f" blockedBy={t.blockedBy}" if t.blockedBy else ""
            lines.append(f"[{t.status}{owner}] {t.id} {t.subject}{deps}")
        return "\n".join(lines)
