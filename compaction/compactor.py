"""ContextCompactor：统一编排三层预处理、LLM 摘要与应急压缩。

prepare / maybe_summarize 是同签名的 PreLLMCall mutator（messages -> messages），
按序挂到 hook 注册表；reactive_compact 仅供 recovery.ErrorRecovery 在 413 时
调用，且只尝试一次，仍超限即放弃（再压不会更小）。
"""

from typing import Any

from . import blocks as B
from . import preprocess as P
from .transcript import write_transcript

# 超过该 token 估算值即触发全量 LLM 摘要
DEFAULT_TOKEN_THRESHOLD = 100_000
# 应急压缩时尾部保留的消息条数
REACTIVE_TAIL_KEEP = 5

SUMMARY_SYSTEM = (
    "You compress an agent's conversation history into a concise summary "
    "that lets the agent continue. Preserve: current goal, important "
    "findings, files created or modified with their paths, pending work, "
    "and user constraints/preferences. Drop raw tool outputs. Be specific "
    "and terse."
)


class CompactDirective:
    """compact 工具返回的循环控制指令：对当前消息执行全量压缩。"""

    def __init__(self, compactor: "ContextCompactor") -> None:
        self.compactor = compactor

    def apply(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.compactor.compact_history(messages, tag="manual")


class ContextCompactor:
    def __init__(
        self,
        llm: Any,
        token_threshold: int = DEFAULT_TOKEN_THRESHOLD,
    ) -> None:
        self.llm = llm
        self.token_threshold = token_threshold

    # -- 0-API --

    def prepare(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return P.run_preprocessors(messages)

    def needs_summary(self, messages: list[dict[str, Any]]) -> bool:
        return B.estimate_tokens(messages) > self.token_threshold

    def maybe_summarize(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """PreLLMCall mutator：超阈值才摘要，否则原样放行。"""
        if self.needs_summary(messages):
            return self.compact_history(messages)
        return messages

    # -- 1-API 摘要 --

    def summarize(self, messages: list[dict[str, Any]]) -> str:
        request = [{
            "role": "user",
            "content": "Summarize this agent conversation:\n\n"
                       + B.messages_to_text(messages),
        }]
        response = self.llm.create(SUMMARY_SYSTEM, request, [])
        return "\n".join(
            b.text for b in response.content
            if getattr(b, "type", None) == "text" and b.text
        )

    def compact_history(
        self, messages: list[dict[str, Any]], tag: str = "compact"
    ) -> list[dict[str, Any]]:
        # 先落完整 transcript，再让模型只带摘要继续
        write_transcript(messages, tag=tag)
        summary = self.summarize(messages)
        return [{
            "role": "user",
            "content": f"[Compacted]\n\n{summary}",
        }]

    def reactive_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """413 应急：摘要之外再保留尾部少量消息，但不制造孤立 tool_result。

        保留的尾部若含超大 tool_result，必须落盘否则单条体积就能再次触发 413。
        """
        write_transcript(messages, tag="reactive")
        summary = self.summarize(messages)

        tail_start = max(0, len(messages) - REACTIVE_TAIL_KEEP)
        if (
            0 < tail_start < len(messages)
            and B.is_tool_result_message(messages[tail_start])
            and B.has_tool_use(messages[tail_start - 1])
        ):
            tail_start -= 1

        result = [{
            "role": "user",
            "content": f"[Reactive compact]\n\n{summary}",
        }, *messages[tail_start:]]

        # 尾部可能含单条超大输出：落盘 + 折叠旧结果，确保体积真正降下来
        P.tool_result_budget(result, scan_all=True)
        P.micro_compact(result)
        return result
