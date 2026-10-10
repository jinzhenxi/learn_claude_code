"""Agent 基类：主/子 Agent 共用的循环骨架（模板方法）。

run() 的流程固定不变；主/子差异全部下沉为可覆写点：
  system_prompt  抽象属性，各自的角色指令
  max_rounds     子 Agent 有上限，默认 None 不限制
  fire_stop      仅主 Agent 结束时触发 Stop 事件
  observe_round  每轮尾部追加的块，默认空（主 Agent 挂 todo 提醒）
"""

from abc import ABC, abstractmethod
from typing import Any

from hooks import HookEvent


class BaseAgent(ABC):
    def __init__(self, llm: Any, registry: Any, hooks: Any) -> None:
        self.llm = llm
        self.registry = registry
        self.hooks = hooks

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
        while True:
            if self.max_rounds is not None and rounds >= self.max_rounds:
                return

            response = self.llm.create(
                self.system_prompt, messages, self.registry.definitions()
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                if self.fire_stop:
                    self.hooks.trigger(HookEvent.STOP, messages)
                return

            results = [self._invoke_tool(block) for block in tool_calls]
            results.extend(self.observe_round())
            messages.append({"role": "user", "content": results})
            rounds += 1

    def _invoke_tool(self, block: Any) -> dict[str, Any]:
        """执行前过 PreToolUse、执行后过 PostToolUse；阻断/失败都回传。"""
        try:
            tool = self.registry.get(block.name)
        except KeyError:
            return self._tool_result(
                block.id, f"Error: unknown tool '{block.name}'", True
            )

        print(f"\033[33m{tool.preview(block.input)}\033[0m")

        # 安全策略由 hook 注册表决定；子 Agent 传入同一注册表，不跳过
        deny_reason = self.hooks.trigger(HookEvent.PRE_TOOL_USE, block)
        if deny_reason is not None:
            print(f"\033[31m[blocked] {deny_reason}\033[0m")
            return self._tool_result(block.id, deny_reason, True)

        result = tool.run(**block.input)
        self.hooks.trigger(HookEvent.POST_TOOL_USE, block, result.content)
        color = "\033[31m" if result.is_error else "\033[32m"
        print(f"{color}{result.content[:200]}\033[0m")
        return self._tool_result(block.id, result.content, result.is_error)

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
