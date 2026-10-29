"""后台任务模块：耗时操作丢到 daemon 线程执行，结果以通知形式回收。"""

from .manager import BackgroundTaskManager
from .policy import is_slow_operation, should_run_background

__all__ = ["BackgroundTaskManager", "should_run_background", "is_slow_operation"]
