"""Hook 层：生命周期事件注册表。

循环只负责在固定时机 trigger 事件，不认识任何具体检查；
要跑什么（权限、日志……）全部由注册表中的回调决定。
返回非 None 的回调会阻断当前事件（PreToolUse 即不执行工具）。
"""

from typing import TYPE_CHECKING, Any, Callable, Optional

from tools import WORKDIR

if TYPE_CHECKING:
    from permission import Permission


class HookEvent:
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"


HookCallback = Callable[..., Optional[str]]


class HookRegistry:
    """事件 -> 回调列表；分发逻辑替代在循环里写检查分支。"""

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookCallback]] = {
            HookEvent.USER_PROMPT_SUBMIT: [],
            HookEvent.PRE_TOOL_USE: [],
            HookEvent.POST_TOOL_USE: [],
            HookEvent.STOP: [],
        }

    def register(self, event: str, callback: HookCallback) -> "HookRegistry":
        # 同事件按注册顺序执行
        self._hooks[event].append(callback)
        return self

    def trigger(self, event: str, *args: Any) -> Optional[str]:
        for callback in self._hooks[event]:
            result = callback(*args)
            # 首个非 None 结果即阻断，后续回调不再执行
            if result is not None:
                return result
        return None


# -- s03 权限逻辑的适配：复用整套 Gate，不改写、只包装 --

class PermissionHook:
    """把 Permission.check 适配为 PreToolUse 回调：放行返回 None，拒绝返回原因。"""

    def __init__(self, permission: "Permission") -> None:
        self.permission = permission

    def __call__(self, block: Any) -> Optional[str]:
        decision = self.permission.check(block.name, block.input)
        return None if decision.allowed else decision.reason


# -- 其余为纯观测类回调，一律返回 None --

def context_inject_hook(query: str) -> Optional[str]:
    """UserPromptSubmit：用户输入送达模型前注入运行上下文提示。"""
    print(f"\033[90m[HOOK] UserPromptSubmit: working in {WORKDIR}\033[0m")
    return None


def log_hook(block: Any) -> Optional[str]:
    """PreToolUse：记录每一次即将执行的工具调用。"""
    args_preview = str(list(block.input.values())[:2])[:60]
    print(f"\033[90m[HOOK] {block.name}({args_preview})\033[0m")
    return None


def large_output_hook(block: Any, output: str) -> Optional[str]:
    """PostToolUse：工具产出过大时给出告警。"""
    if len(str(output)) > 100000:
        print(
            f"\033[33m[HOOK] Large output from {block.name}: "
            f"{len(str(output))} chars\033[0m"
        )
    return None


def summary_hook(messages: list[dict[str, Any]]) -> Optional[str]:
    """Stop：循环退出前统计本轮工具调用次数。"""
    tool_count = sum(
        1
        for m in messages
        for b in (m.get("content") if isinstance(m.get("content"), list) else [])
        if isinstance(b, dict) and b.get("type") == "tool_result"
    )
    print(f"\033[90m[HOOK] Stop: session used {tool_count} tool calls\033[0m")
    return None


def build_default_hooks(permission: "Permission") -> HookRegistry:
    """默认挂载点；新增回调在这里加一行即可，循环无需改动。"""
    hooks = HookRegistry()
    hooks.register(HookEvent.USER_PROMPT_SUBMIT, context_inject_hook)
    # 权限先于日志：被阻断的调用不再进入“即将执行”日志
    hooks.register(HookEvent.PRE_TOOL_USE, PermissionHook(permission))
    hooks.register(HookEvent.PRE_TOOL_USE, log_hook)
    hooks.register(HookEvent.POST_TOOL_USE, large_output_hook)
    hooks.register(HookEvent.STOP, summary_hook)
    return hooks
