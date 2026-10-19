"""Hook 层：生命周期事件注册表。

循环只负责在固定时机 trigger 事件，不认识任何具体检查；要跑什么全部由注册表决定。
两条通道语义分离：
  观察者/拦截器 trigger：返回非 None 字符串即阻断当前事件（PreToolUse 不执行工具）。
  加工器     apply：payload 依次流过各 mutator 接力变换（如调用前压缩 messages）。
"""

from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    # 类型仅用于注解；运行时不导入 tools 以免 hooks <-> tools 循环依赖
    from permission import Permission


class HookEvent:
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_LLM_CALL = "PreLLMCall"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    STOP = "Stop"


HookCallback = Callable[..., Optional[str]]
Mutator = Callable[[Any], Any]


class HookRegistry:
    """事件 -> 回调列表；观察者走 trigger 短路阻断，加工器走 apply 接力变换。"""

    def __init__(self) -> None:
        events = (
            HookEvent.USER_PROMPT_SUBMIT,
            HookEvent.PRE_LLM_CALL,
            HookEvent.PRE_TOOL_USE,
            HookEvent.POST_TOOL_USE,
            HookEvent.STOP,
        )
        self._hooks: dict[str, list[HookCallback]] = {e: [] for e in events}
        self._mutators: dict[str, list[Mutator]] = {e: [] for e in events}

    def register(self, event: str, callback: HookCallback) -> "HookRegistry":
        # 同事件按注册顺序执行
        self._hooks[event].append(callback)
        return self

    def register_mutator(self, event: str, mutator: Mutator) -> "HookRegistry":
        """注册 payload -> payload 加工器；同事件按注册顺序接力。"""
        self._mutators[event].append(mutator)
        return self

    def trigger(self, event: str, *args: Any) -> Optional[str]:
        for callback in self._hooks[event]:
            result = callback(*args)
            # 首个非 None 结果即阻断，后续回调不再执行
            if result is not None:
                return result
        return None

    def apply(self, event: str, payload: Any) -> Any:
        """让某事件的全部 mutator 依次加工 payload，返回最终结果。"""
        for mutator in self._mutators[event]:
            payload = mutator(payload)
        return payload


# -- s03 权限逻辑的适配：复用整套 Gate，不改写、只包装 --

class PermissionHook:
    """把 Permission.check 适配为 PreToolUse 回调：放行返回 None，拒绝返回原因。"""

    def __init__(self, permission: "Permission") -> None:
        self.permission = permission

    def __call__(self, block: Any) -> Optional[str]:
        decision = self.permission.check(block.name, block.input)
        return None if decision.allowed else decision.reason


# -- 其余为纯观测类回调，一律返回 None --

def context_inject_hook(user_msg: dict[str, Any]) -> Optional[str]:
    """UserPromptSubmit：用户输入送达模型前注入运行上下文提示。

    payload 是完整的 user message dict；observer 只观测不修改，
    记忆注入等改写走 register_mutator。
    """
    # 延迟导入：模块加载期避开 hooks -> tools -> agent -> hooks 的环
    from tools import WORKDIR

    query = str(user_msg.get("content", ""))
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
