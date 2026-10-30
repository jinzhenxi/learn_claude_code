"""Cron 队列处理器：交付端。

不检查时间，只负责在队列有任务且 Agent 空闲时拉起一轮执行。
通过 agent_lock 与用户发起的 turn 互斥：同一时刻只有一个 Agent turn 在跑。

生产者（调度线程）→ fired 队列 → 交付者（本处理器）→ 消费者（agent.run）
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .scheduler import CronScheduler


class CronProcessor:
    def __init__(
        self,
        scheduler: "CronScheduler",
        agent: Any,
        history: list[dict[str, Any]],
        agent_lock: threading.Lock,
    ) -> None:
        self.scheduler = scheduler
        self.agent = agent
        self.history = history
        self.agent_lock = agent_lock
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="cron-processor"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _loop(self) -> None:
        while self._running:
            try:
                if not self.scheduler.has_fired_jobs():
                    time.sleep(0.2)
                    continue
                # Agent 忙则跳过，等下一轮
                if not self.agent_lock.acquire(blocking=False):
                    time.sleep(0.2)
                    continue
                try:
                    fired = self.scheduler.consume_fired_jobs()
                    if not fired:
                        continue
                    self._run_turn(fired)
                finally:
                    self.agent_lock.release()
            except Exception as e:
                print(f"[cron] processor error: {e}")
            time.sleep(0.2)

    def _run_turn(self, fired: list) -> None:
        """把已触发的 cron job 注入 messages 并执行一轮。"""
        for job in fired:
            self.history.append({
                "role": "user",
                "content": f"[Scheduled] {job.prompt}",
            })
        try:
            self.agent.run(self.history)
        except Exception as e:
            print(f"[cron] agent turn error: {e}")
            return
        # 打印本轮最终答复的 text 块（与 REPL 行为一致）
        response_content = self.history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if getattr(block, "type", None) == "text":
                    print(block.text)
        print()
