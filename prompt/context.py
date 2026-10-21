"""System prompt 上下文：从真实状态组装，不做关键词猜测。

context 是 assemble_system_prompt 的唯一输入；其字段全部来自运行时真实对象
（工具注册表、workdir、memory 索引、skills 目录），保证确定性和可缓存性。
"""

from __future__ import annotations

import os
from typing import Any

from .sections import MEMORY_HEADER


def build_context(
    agent_type: str,
    registry: Any,
    skills: Any = None,
    memory: Any = None,
) -> dict[str, Any]:
    """根据真实对象组装 prompt context。

    agent_type: "main" | "sub"
    registry:   ToolManager，取已注册工具名
    skills:     SkillManager 或 None，取目录文本
    memory:     MemoryManager 或 None，取索引文本
    """
    enabled_tools = list(registry._tools.keys()) if registry is not None else []

    skills_catalog = ""
    if skills is not None:
        catalog = skills.catalog()
        if catalog:
            skills_catalog = catalog

    memories = ""
    if memory is not None:
        idx = memory.index_text()
        if idx:
            memories = f"{MEMORY_HEADER}\n{idx}"

    return {
        "agent_type": agent_type,
        "workspace": os.getcwd(),
        "enabled_tools": enabled_tools,
        "skills_catalog": skills_catalog,
        "memories": memories,
    }
