"""三层 0-API 预处理器，每轮 LLM 调用前依次执行。

顺序固定：budget（大结果落盘）→ snip（裁旧对话中段）→ micro（旧结果占位）。
三者都只做本地消息变换，绝不触发模型调用。
"""

from typing import Any

from . import blocks as B
from .paths import MAX_TOOL_OUTPUT_FILES, TOOL_OUTPUT_DIR, rotate, safe_filename

# 单轮 tool_result 总量上限（字节）
RESULT_BUDGET_BYTES = 200_000
# 消息条数上限：超过则裁中段，保留头部初始上下文与尾部当前工作
MAX_MESSAGES = 50
HEAD_KEEP = 3
# micro：只保留最近 N 条 tool_result 的完整内容
KEEP_RECENT_TOOL_RESULTS = 3
MICRO_MIN_LEN = 120


def persist_large_output(tool_use_id: str, content: str) -> str:
    """把大结果写到 .tool_outputs/，返回可重新读取的占位文本。"""
    TOOL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{safe_filename(tool_use_id)}.txt"
    path = TOOL_OUTPUT_DIR / file_name
    path.write_text(content, encoding="utf-8")
    rotate(TOOL_OUTPUT_DIR, MAX_TOOL_OUTPUT_FILES)
    rel = path.relative_to(TOOL_OUTPUT_DIR.parent)
    return (
        f"[Large output persisted to {rel} ({len(content)} chars). "
        "Use read_file or bash if you need it.]"
    )


def tool_result_budget(
    messages: list[dict[str, Any]],
    max_bytes: int = RESULT_BUDGET_BYTES,
    scan_all: bool = False,
) -> list[dict[str, Any]]:
    """把超大 tool_result 落盘并替换为占位符。

    scan_all=False（默认，常规路径）：仅看最新一条 user 消息——单轮工具结果
    都集中在最后一条里。scan_all=True（应急路径）：扫所有 user 消息，
    因为 reactive 保留的尾部可能包含多个待发送 result。
    """
    targets = messages if scan_all else (messages[-1:] if messages else [])

    def size(b: dict[str, Any]) -> int:
        return len(str(b.get("content", "")))

    for message in targets:
        blocks = B.message_blocks(message)
        result_blocks = [
            b for b in blocks
            if isinstance(b, dict) and B.block_type(b) == "tool_result"
        ]
        total = sum(size(b) for b in result_blocks)
        if total <= max_bytes:
            continue
        ranked = sorted(result_blocks, key=size, reverse=True)
        for block in ranked:
            if total <= max_bytes:
                break
            content = str(block.get("content", ""))
            block["content"] = persist_large_output(
                block.get("tool_use_id", "x"), content
            )
            total = sum(size(b) for b in result_blocks)
    return messages


def snip_compact(
    messages: list[dict[str, Any]], max_messages: int = MAX_MESSAGES
) -> list[dict[str, Any]]:
    """消息过多时裁掉中段；绝不拆散 tool_use 与其 tool_result。

    输出目标 ≤ max_messages；占位符本身占一条，故尾部配额为
    max_messages - HEAD_KEEP - 1。头部因保对而扩展时，可能略超上限，
    但正确性（不拆对）优先于精确配额。
    """
    if len(messages) <= max_messages:
        return messages

    head_end = HEAD_KEEP

    # 头部切分点若落在 tool_use 上，连带把它的 tool_result 消息划进保留头
    if head_end < len(messages) and B.has_tool_use(messages[head_end - 1]):
        while head_end < len(messages) and B.is_tool_result_message(
            messages[head_end]
        ):
            head_end += 1

    # 尾部配额：max - 头 - 占位符 - 可能的尾部回退保对(1)
    # 基态输出 = head_end + 1 + tail_quota = max - 1；回退保对后恰好 = max
    tail_quota = max_messages - head_end - 2
    if tail_quota <= 0:
        # 头部扩展吃光了配额，无安全切点，放弃本轮
        return messages
    tail_start = len(messages) - tail_quota

    # 尾部起点若是孤立 tool_result，优先连同其 tool_use 一起保留进尾部
    if (
        tail_start > head_end
        and B.is_tool_result_message(messages[tail_start])
        and B.has_tool_use(messages[tail_start - 1])
    ):
        tail_start -= 1

    # 后退会与头部相撞时改为前进：让边界整对落入被裁中段，不能让 tail 以孤立 result 开头
    if tail_start <= head_end:
        tail_start = head_end + 1
        while (
            tail_start < len(messages)
            and B.is_tool_result_message(messages[tail_start])
        ):
            tail_start += 1
        # 一路前进到尾仍无安全切点（末尾是待发送 result）：放弃本轮，交给其它压缩层
        if tail_start >= len(messages):
            return messages

    snipped = tail_start - head_end
    placeholder = {
        "role": "user",
        "content": f"[snipped {snipped} messages from conversation middle]",
    }
    return messages[:head_end] + [placeholder] + messages[tail_start:]


def micro_compact(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """旧 tool_result 折叠为一行占位，只保留最近 N 条的完整内容。"""
    results = list(B.iter_tool_result_blocks(messages))
    if len(results) <= KEEP_RECENT_TOOL_RESULTS:
        return messages
    for _, _, block in results[:-KEEP_RECENT_TOOL_RESULTS]:
        if len(str(block.get("content", ""))) > MICRO_MIN_LEN:
            block["content"] = "[Earlier tool result compacted. Re-run if needed.]"
    return messages


def run_preprocessors(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """三层串联，顺序不可换：先落盘再占位/裁剪。"""
    messages = tool_result_budget(messages)
    messages = snip_compact(messages)
    messages = micro_compact(messages)
    return messages
