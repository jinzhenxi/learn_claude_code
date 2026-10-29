"""后台任务管理器：daemon 线程执行 + 状态追踪 + 通知回收。

两个 hook 切点：
  PRE_TOOL_USE  判定后台执行 → 启动线程 → 返回 ToolResult 占位（跳过同步执行）
  PRE_LLM_CALL  下一轮调用前收集已完成任务，注入 <task_notification>

主循环 run() 完全不感知后台逻辑。
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from hooks import HookEvent
from tools.base_tool import ToolResult

from .policy import should_run_background

if TYPE_CHECKING:
    from hooks import HookRegistry
    from tools import ToolManager


class BackgroundTaskManager:
    def __init__(self, registry: "ToolManager") -> None:
        # 持有注册表以便后台线程中查找工具实例（主/子管理器共享同一批基础工具）
        self.registry = registry
        self._counter = 0
        self._tasks: dict[str, dict] = {}       # bg_id -> {tool_use_id, command, status}
        self._results: dict[str, str] = {}      # bg_id -> output
        self._lock = threading.Lock()

    # -- ID --

    def _next_id(self) -> str:
        self._counter += 1
        return f"bg_{self._counter:04d}"

    # -- 启动 --

    def start(self, block: Any) -> str:
        """把工具调用包成 worker 扔到 daemon 线程，返回后台任务 ID。"""
        bg_id = self._next_id()
        command = block.input.get("command", "")

        def worker() -> None:
            try:
                tool = self.registry.get(block.name)
                # run_in_background 是给 hook 看的，工具本身不消费，需剔除
                tool_input = {
                    k: v for k, v in block.input.items()
                    if k != "run_in_background"
                }
                result = tool.run(**tool_input)
                output = result.content
            except Exception as e:
                output = f"Error: {type(e).__name__}: {e}"
            with self._lock:
                self._tasks[bg_id]["status"] = "completed"
                self._results[bg_id] = output

        with self._lock:
            self._tasks[bg_id] = {
                "tool_use_id": block.id,
                "command": command,
                "status": "running",
            }
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return bg_id

    # -- 回收 --

    def collect_notifications(self) -> list[str]:
        """收集已完成任务的通知文本，并从内部状态移除。"""
        with self._lock:
            ready = [
                bid for bid, task in self._tasks.items()
                if task["status"] == "completed"
            ]
        notifications: list[str] = []
        for bg_id in ready:
            with self._lock:
                task = self._tasks.pop(bg_id, None)
                output = self._results.pop(bg_id, "")
            if task is None:
                continue
            notifications.append(
                f"<task_notification>\n"
                f"  <task_id>{bg_id}</task_id>\n"
                f"  <status>completed</status>\n"
                f"  <command>{task['command']}</command>\n"
                f"  <summary>{output[:200]}</summary>\n"
                f"</task_notification>"
            )
        return notifications

    # -- Hook 回调 --

    def on_pre_tool_use(self, block: Any) -> ToolResult | None:
        """PRE_TOOL_USE 拦截器：命中后台则启动线程并返回占位结果。"""
        if not should_run_background(block.name, block.input):
            return None
        bg_id = self.start(block)
        return ToolResult(
            content=f"[Background task {bg_id} started] "
                    f"Result will be available when complete."
        )

    def on_pre_llm_call(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """PRE_LLM_CALL mutator：把已完成任务的通知注入最后一条 user 消息。"""
        notifications = self.collect_notifications()
        if not notifications:
            return messages
        blocks = [{"type": "text", "text": n} for n in notifications]
        if messages and messages[-1].get("role") == "user":
            content = messages[-1]["content"]
            if isinstance(content, list):
                content.extend(blocks)
            else:
                # 字符串内容转列表后追加通知
                messages[-1]["content"] = (
                    [{"type": "text", "text": content}] + blocks
                )
        else:
            messages.append({"role": "user", "content": blocks})
        return messages

    # -- 注册 --

    def register_hooks(self, hooks: "HookRegistry") -> None:
        """注册到 hook 注册表。

        PRE_TOOL_USE 必须在 PermissionHook / log_hook 之后注册：
        权限闸门先过，再由本管理器决定是否后台执行。
        """
        hooks.register(HookEvent.PRE_TOOL_USE, self.on_pre_tool_use)
        hooks.register_mutator(HookEvent.PRE_LLM_CALL, self.on_pre_llm_call)
