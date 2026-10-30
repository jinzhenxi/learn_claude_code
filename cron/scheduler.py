"""Cron 调度器：独立 daemon 线程每秒轮询，匹配后放入 fired 队列。

生产者角色：只负责"到点了就入队"，不关心谁来消费、Agent 是否空闲。
单次 job 异常被 try/except 吞掉，不会拖垮整个调度线程。
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .job import CronJob
from .parser import cron_matches, validate_cron

WORKDIR = Path.cwd().resolve()
CRON_DIR = WORKDIR / ".cron"
DURABLE_FILE = CRON_DIR / "jobs.json"


def _new_job_id() -> str:
    return f"cron_{int(time.time())}_{secrets.token_hex(3)}"


class CronScheduler:
    def __init__(self, durable_file: Path = DURABLE_FILE) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._fired: list[CronJob] = []
        self._last_fired: dict[str, str] = {}  # job_id -> "YYYY-MM-DD HH:MM"
        self._lock = threading.Lock()
        self._durable_file = durable_file
        self._running = False
        self._thread: threading.Thread | None = None
        self._load_durable()

    # -- 任务管理 --

    def add_job(
        self,
        cron: str,
        prompt: str,
        recurring: bool = True,
        durable: bool = True,
    ) -> tuple[str | None, str | None]:
        """注册一个 cron 任务。返回 (job_id, error)；失败时 job_id 为 None。"""
        err = validate_cron(cron)
        if err:
            return None, f"invalid cron expression: {err}"
        job = CronJob(
            id=_new_job_id(),
            cron=cron,
            prompt=prompt,
            recurring=recurring,
            durable=durable,
        )
        with self._lock:
            self._jobs[job.id] = job
        if durable:
            self._save_durable()
        return job.id, None

    def remove_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        if job.durable:
            self._save_durable()
        return True

    def list_jobs(self) -> list[CronJob]:
        with self._lock:
            return list(self._jobs.values())

    # -- fired 队列 --

    def has_fired_jobs(self) -> bool:
        with self._lock:
            return len(self._fired) > 0

    def consume_fired_jobs(self) -> list[CronJob]:
        """取出并清空已触发队列。"""
        with self._lock:
            fired = self._fired
            self._fired = []
            return fired

    # -- 调度线程 --

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="cron-scheduler"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _scheduler_loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as e:
                print(f"[cron] scheduler tick error: {e}")
            time.sleep(1)

    def _tick(self) -> None:
        now = datetime.now()
        minute_marker = now.strftime("%Y-%m-%d %H:%M")
        one_shot_removed = False
        with self._lock:
            for job in list(self._jobs.values()):
                try:
                    if not cron_matches(job.cron, now):
                        continue
                    if self._last_fired.get(job.id) == minute_marker:
                        continue
                    self._fired.append(job)
                    self._last_fired[job.id] = minute_marker
                    if not job.recurring:
                        self._jobs.pop(job.id, None)
                        if job.durable:
                            one_shot_removed = True
                except Exception as e:
                    print(f"[cron] job {job.id} error: {e}")
        if one_shot_removed:
            self._save_durable()

    # -- 持久化 --

    def _load_durable(self) -> None:
        if not self._durable_file.exists():
            return
        try:
            data = json.loads(self._durable_file.read_text(encoding="utf-8"))
            for item in data:
                job = CronJob.from_dict(item)
                self._jobs[job.id] = job
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[cron] failed to load durable jobs: {e}")

    def _save_durable(self) -> None:
        self._durable_file.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            durable = [j.to_dict() for j in self._jobs.values() if j.durable]
        self._durable_file.write_text(
            json.dumps(durable, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
