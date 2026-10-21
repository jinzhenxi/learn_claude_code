"""System prompt 组装器：按需拼接 + 缓存。

assemble_system_prompt(context)：始终加载 identity/tools/workspace，
按需加载 skills/memories/todo/task（基于真实状态，非关键词）。

get_system_prompt(context)：用 json.dumps 做稳定 cache key，context 不变
时直接返回缓存，避免每轮重复拼接字符串。这是进程内的拼接缓存，和 CC 的
API prompt cache 是两回事。
"""

from __future__ import annotations

import json
from typing import Any

from .sections import (
    IDENTITY_MAIN,
    IDENTITY_SUB,
    TASK_HINT,
    TODO_HINT,
    TOOLS_GUIDANCE,
)


def assemble_system_prompt(context: dict[str, Any]) -> str:
    """按真实状态拼接段落；无关 section 不加载，省 token 也减噪音。"""
    sections: list[str] = []

    # 始终加载
    agent_type = context.get("agent_type", "main")
    sections.append(IDENTITY_MAIN if agent_type == "main" else IDENTITY_SUB)
    sections.append(f"Working directory: {context.get('workspace', '')}")
    sections.append(TOOLS_GUIDANCE)

    enabled_tools = context.get("enabled_tools", [])

    # 按需加载 — 基于真实状态
    if "todo_write" in enabled_tools:
        sections.append(TODO_HINT)
    if "task" in enabled_tools:
        sections.append(TASK_HINT)

    skills_catalog = context.get("skills_catalog", "")
    if skills_catalog:
        sections.append(skills_catalog)

    memories = context.get("memories", "")
    if memories:
        sections.append(memories)

    return "\n\n".join(sections)


class PromptManager:
    """持有单条缓存的 system prompt 组装器。

    每个 Agent 持有一个实例；主/子互不污染。context 变了才重新拼接。
    """

    def __init__(self) -> None:
        self._last_key: str | None = None
        self._last_prompt: str | None = None

    @staticmethod
    def _cache_key(context: dict[str, Any]) -> str:
        # json.dumps + sort_keys 是稳定的；hash() 有进程随机化且不支持 dict/list
        return json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)

    def get_system_prompt(self, context: dict[str, Any]) -> str:
        key = self._cache_key(context)
        if key == self._last_key and self._last_prompt is not None:
            return self._last_prompt
        self._last_key = key
        self._last_prompt = assemble_system_prompt(context)
        return self._last_prompt
