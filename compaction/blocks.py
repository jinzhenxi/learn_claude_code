"""消息块工具：归一化访问 dict（user 侧）与 SDK 对象（assistant 侧）。

压缩时最关键的不变量：assistant(tool_use) 与其后 user(tool_result)
必须成对，任何裁剪都不能留下孤立块，否则 API 直接 400。
"""

from typing import Any


def block_type(block: Any) -> str:
    if isinstance(block, dict):
        return block.get("type", "")
    return getattr(block, "type", "")


def message_blocks(message: dict[str, Any]) -> list[Any]:
    content = message.get("content")
    return content if isinstance(content, list) else []


def has_tool_use(message: dict[str, Any]) -> bool:
    return any(block_type(b) == "tool_use" for b in message_blocks(message))


def is_tool_result_message(message: dict[str, Any]) -> bool:
    if message.get("role") != "user":
        return False
    return any(
        block_type(b) == "tool_result" for b in message_blocks(message)
    )


def iter_tool_result_blocks(messages: list[dict[str, Any]]):
    """产出 (消息下标, 块下标, dict 块)，按时间先后。"""
    for mi, message in enumerate(messages):
        for bi, block in enumerate(message_blocks(message)):
            if isinstance(block, dict) and block_type(block) == "tool_result":
                yield mi, bi, block


def block_text(block: Any) -> str:
    """把任意块转成可读文本，供摘要与 token 估算使用。"""
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        kind = block.get("type", "text")
        if kind == "text":
            return str(block.get("text", ""))
        if kind == "tool_result":
            return str(block.get("content", ""))
        if kind == "tool_use":
            return f"[tool_use {block.get('name')}] {block.get('input')}"
        return str(block)
    # SDK 对象
    kind = block_type(block)
    if kind == "text":
        return getattr(block, "text", "")
    if kind == "tool_use":
        return f"[tool_use {getattr(block, 'name', '')}] {getattr(block, 'input', {})}"
    return str(block)


def messages_to_text(messages: list[dict[str, Any]]) -> str:
    lines = []
    for message in messages:
        role = message.get("role", "?")
        content = message.get("content")
        if isinstance(content, list):
            body = "\n".join(block_text(b) for b in content)
        else:
            body = str(content)
        lines.append(f"### {role}\n{body}")
    return "\n\n".join(lines)


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """粗估 token：字符数 / 4，0 API。"""
    return len(messages_to_text(messages)) // 4


def to_jsonable(obj: Any) -> Any:
    """JSON 序列化兜底：SDK 的 pydantic 块走 model_dump。"""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)
