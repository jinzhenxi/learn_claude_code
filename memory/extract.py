"""记忆提取：每轮结束后从对话中提取稳定偏好/事实，持久化为记忆。

- extract_memories：只看最近 10 条对话，带上已有记忆清单让 LLM 判重，避免重复写入。
- consolidate_memories：文件数 ≥ CONSOLIDATE_THRESHOLD 时，让 LLM 去重、合并矛盾、淘汰过时。
"""

from __future__ import annotations

import json
import re
from typing import Any

from .store import MemoryManager

# 提取时只看最近 N 条，控制 token
RECENT_MESSAGES = 10
# 文件数达到该阈值触发整理
CONSOLIDATE_THRESHOLD = 10

_EXTRACT_SYSTEM = (
    "You extract durable knowledge from a conversation into long-term memory. "
    "Only extract stable user preferences, habits, constraints, or important "
    "project facts. Do NOT extract transient task details, one-off requests, "
    "or information already covered by existing memories.\n"
    "Return ONLY a JSON array of objects: "
    "[{\"name\": \"slug-name\", \"description\": \"one line\", \"type\": \"user|project|fact\", "
    "\"content\": \"why and how to apply\"}]. "
    "Return [] if nothing new is worth remembering."
)

_CONSOLIDATE_SYSTEM = (
    "You consolidate a set of long-term memories. Deduplicate semantically "
    "redundant entries, merge conflicting ones (prefer the more recent/specific), "
    "and drop outdated or trivial ones. Return ONLY a JSON array of the "
    "surviving memories with the same schema: "
    "[{\"name\", \"description\", \"type\", \"content\"}]."
)

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _messages_to_text(messages: list[dict[str, Any]]) -> str:
    lines = []
    for m in messages[-RECENT_MESSAGES:]:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, list):
            texts = [
                b.get("text", "") if isinstance(b, dict) else getattr(b, "text", "")
                for b in content
            ]
            content = " ".join(t for t in texts if t)
        lines.append(f"{role}: {str(content)[:2000]}")
    return "\n".join(lines)


def _parse_memory_array(text: str) -> list[dict[str, str]]:
    m = _JSON_ARRAY_RE.search(text)
    if not m:
        return []
    data = json.loads(m.group(0))
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        type_ = str(item.get("type", "fact")).strip() or "fact"
        content = str(item.get("content", "")).strip()
        if name and description and content:
            result.append({
                "name": name,
                "description": description,
                "type": type_,
                "content": content,
            })
    return result


def _existing_summary(manager: MemoryManager) -> str:
    memories = manager.list_memories()
    if not memories:
        return "(none)"
    return "\n".join(f"- {m.name}: {m.description}" for m in memories)


def extract_memories(
    llm: Any, messages: list[dict[str, Any]], manager: MemoryManager
) -> list[dict[str, str]]:
    """让 LLM 从最近对话中提取新记忆。带上已有记忆避免重复。失败返回空列表。"""
    if not messages:
        return []
    transcript = _messages_to_text(messages)
    existing = _existing_summary(manager)
    user_msg = (
        f"Existing memories:\n{existing}\n\n"
        f"Recent dialogue:\n{transcript}\n\n"
        f"Extract NEW durable memories not already covered. JSON array:"
    )
    try:
        response = llm.create(
            _EXTRACT_SYSTEM, [{"role": "user", "content": user_msg}], []
        )
        text = "\n".join(
            b.text for b in response.content
            if getattr(b, "type", None) == "text" and b.text
        )
        return _parse_memory_array(text)
    except Exception:
        return []


def consolidate_memories(
    llm: Any, manager: MemoryManager
) -> list[str] | None:
    """文件数达阈值时让 LLM 整理：去重、合并矛盾、淘汰过时。返回新 name 列表，未触发返回 None。"""
    memories = manager.list_memories()
    if len(memories) < CONSOLIDATE_THRESHOLD:
        return None
    all_text = "\n\n".join(
        f"[{m.name}] ({m.type}) {m.description}\n{m.content}" for m in memories
    )
    user_msg = (
        f"Consolidate these memories. Deduplicate, merge conflicts, drop outdated.\n\n"
        f"{all_text}\n\nReturn JSON array of surviving memories:"
    )
    try:
        response = llm.create(
            _CONSOLIDATE_SYSTEM, [{"role": "user", "content": user_msg}], []
        )
        text = "\n".join(
            b.text for b in response.content
            if getattr(b, "type", None) == "text" and b.text
        )
        consolidated = _parse_memory_array(text)
        if not consolidated:
            # LLM 返回空意味着全部淘汰——保险起见保留原样
            return None
        return manager.replace_all(consolidated)
    except Exception:
        return None


def extract_and_save(
    llm: Any, messages: list[dict[str, Any]], manager: MemoryManager
) -> list[str]:
    """提取新记忆并保存；保存后若文件数达阈值触发整理。返回新保存的 name 列表。"""
    candidates = extract_memories(llm, messages, manager)
    saved: list[str] = []
    for c in candidates:
        # 同名已存在则跳过（避免每轮重复写入）
        if manager.read(c["name"]) is not None:
            continue
        manager.save(c["name"], c["description"], c["type"], c["content"])
        saved.append(c["name"])
    # 写入后检查是否需要整理
    if saved:
        consolidate_memories(llm, manager)
    return saved
