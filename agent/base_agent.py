"""Agent 基类：主/子 Agent 共用的循环骨架（模板方法）。

run() 的流程固定不变；主/子差异全部下沉为可覆写点：
  system_prompt  抽象属性，各自的角色指令
  max_rounds     子 Agent 有上限，默认 None 不限制
  fire_stop      仅主 Agent 结束时触发 Stop 事件
  observe_round  每轮尾部追加的块，默认空（主 Agent 挂 todo 提醒）

上下文如何加工由 PreLLMCall 上的 mutator（如压缩）决定，循环只触发切点；
413 应急重试与工具控制指令属于控制流，仍由循环骨架负责。
"""

from abc import ABC, abstractmethod
from typing import Any

from client import PromptTooLongError
from hooks import HookEvent

# 413 应急压缩的连续失败熔断次数
MAX_REACTIVE_RETRIES = 3


class BaseAgent(ABC):
    def __init__(
        self,
        llm: Any,
        registry: Any,
        hooks: Any,
        compactor: Any = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.hooks = hooks
        self.compactor = compactor

    # -- 子类覆写点 --

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """角色指令；具体 Agent 必须提供。"""

    @property
    def max_rounds(self) -> int | None:
        return None

    @property
    def fire_stop(self) -> bool:
        return True

    def observe_round(self) -> list[dict[str, Any]]:
        """每轮工具执行完追加的块，默认无。"""
        return []

    # -- 固定骨架 --

    def run(self, messages: list[dict[str, Any]]) -> None:
        """就地读写 messages；不再有工具调用时结束。"""
        rounds = 0
        reactive_retries = 0
        while True:
            if self.max_rounds is not None and rounds >= self.max_rounds:
                return

            # task08，压缩策略：PRE_LLM_CALL 触发常规压缩（prepare + maybe_summarize），循环只透传 messages
            messages[:] = self.hooks.apply(HookEvent.PRE_LLM_CALL, messages)

            try:
                response = self.llm.create(
                    self.system_prompt, messages, self.registry.definitions()
                )
            except PromptTooLongError:
                # task08，压缩策略：413 应急兜底，reactive_compact 强裁，连续失败超阈值熔断
                if (
                    self.compactor is not None
                    and reactive_retries < MAX_REACTIVE_RETRIES
                ):
                    reactive_retries += 1
                    messages[:] = self.compactor.reactive_compact(messages)
                    continue
                raise
            reactive_retries = 0

            messages.append({"role": "assistant", "content": response.content})

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                if self.fire_stop:
                    self.hooks.trigger(HookEvent.STOP, messages)
                return

            directive = None
            results = []
            for block in tool_calls:
                result, control = self._invoke_tool(block)
                if control is not None:
                    directive = control
                results.append(result)

            if directive is not None:
                # task08，压缩策略：模型主动调用 compact 工具，由 CompactDirective.apply 执行摘要替换
                messages[:] = directive.apply(messages)
                continue

            results.extend(self.observe_round())
            messages.append({"role": "user", "content": results})
            rounds += 1

    def _invoke_tool(self, block: Any) -> tuple[dict[str, Any], Any]:
        """执行前过 PreToolUse、执行后过 PostToolUse；返回 (结果, 控制指令)。"""
        try:
            tool = self.registry.get(block.name)
        except KeyError:
            return self._tool_result(
                block.id, f"Error: unknown tool '{block.name}'", True
            ), None

        print(f"\033[33m{tool.preview(block.input)}\033[0m")

        # 安全策略由 hook 注册表决定；子 Agent 传入同一注册表，不跳过
        deny_reason = self.hooks.trigger(HookEvent.PRE_TOOL_USE, block)
        if deny_reason is not None:
            print(f"\033[31m[blocked] {deny_reason}\033[0m")
            return self._tool_result(block.id, deny_reason, True), None

        result = tool.run(**block.input)
        self.hooks.trigger(HookEvent.POST_TOOL_USE, block, result.content)
        color = "\033[31m" if result.is_error else "\033[32m"
        print(f"{color}{result.content[:200]}\033[0m")
        return (
            self._tool_result(block.id, result.content, result.is_error),
            result.directive,
        )

    @staticmethod
    def extract_text(content: Any) -> str:
        """只取 assistant 消息中的 text，中间过程全部丢弃。"""
        if not isinstance(content, list):
            return str(content)
        texts = [
            b.text for b in content if getattr(b, "type", None) == "text" and b.text
        ]
        return "\n".join(texts) or "(subagent produced no final text)"

    @staticmethod
    def _tool_result(tool_use_id: str, content: str, is_error: bool) -> dict[str, Any]:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
            "is_error": is_error,
        }
