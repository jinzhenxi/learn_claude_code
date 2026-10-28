"""Task 持久化层：.tasks/{id}.json，外加进程内/跨进程两把锁。

- threading.RLock：同一进程内主 Agent 与多个子 Agent 并发认领时串行化。
- fcntl.flock(.tasks/.lock)：多个 agent 进程操作同一项目时跨进程互斥。
store 只管读写与互斥，不解释状态机（状态规则在 service 层）。
"""

from __future__ import annotations

import fcntl
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .task import Task

WORKDIR = Path.cwd().resolve()
TASK_DIR = WORKDIR / ".tasks"


class TaskNotFoundError(KeyError):
    """任务 ID 不存在。"""


class TaskStore:
    # 绑定落盘目录，初始化进程内可重入锁
    def __init__(self, task_dir: Path = TASK_DIR) -> None:
        self.dir = task_dir
        self._thread_lock = threading.RLock()
        self._fh = None

    # 拼出任务 JSON 文件的绝对路径
    def path_for(self, task_id: str) -> Path:
        return self.dir / f"{task_id}.json"

    # 判断指定任务文件是否已落盘
    def exists(self, task_id: str) -> bool:
        return self.path_for(task_id).exists()

    # -- 锁：读-改-写的状态迁移必须整体持锁 --

    # 进程内 RLock + 文件 flock，串行化状态迁移的读改写
    @contextmanager
    def locked(self) -> Iterator[None]:
        self.dir.mkdir(parents=True, exist_ok=True)
        with self._thread_lock:
            with open(self.dir / ".lock", "w") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    # -- CRUD --

    # 把任务序列化为 JSON 写入 .tasks/{id}.json
    def save(self, task: Task) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path_for(task.id).write_text(
            json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 从 JSON 读回任务，不存在则抛 TaskNotFoundError
    def load(self, task_id: str) -> Task:
        path = self.path_for(task_id)
        if not path.exists():
            raise TaskNotFoundError(task_id)
        return Task.from_dict(json.loads(path.read_text(encoding="utf-8")))

    # 按文件名排序，加载目录下全部任务
    def all(self) -> list[Task]:
        if not self.dir.exists():
            return []
        tasks = [
            Task.from_dict(json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(self.dir.glob("task_*.json"))
        ]
        return tasks
