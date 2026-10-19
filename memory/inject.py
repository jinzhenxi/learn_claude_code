"""记忆注入：两条路径。

路径一：索引常驻 SYSTEM（MemoryManager.index_text，由 MainAgent.system_prompt 调用）。
路径二：相关记忆按需注入当前 user turn（side-query 选相关，失败降级关键词匹配）。
"""

from __future__ import annotations

import json
import re
from typing import Any

from .store import Memory, MemoryManager

# 最多注入的记忆条数
MAX_INJECTED = 5

# side-query 的 system 指令
_SELECT_SYSTEM = (
    "You select which stored memories are relevant to the user's current message. "
    "Return ONLY a JSON array of memory names, e.g. [\"tabs-pref\", \"project-x\"]. "
    "Return [] if none are relevant. Do not explain."
)

# 兜底：JSON 数组抽取
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def system_index_text(manager: MemoryManager) -> str:
    """路径一：MEMORY.md 全文，常驻 system prompt。空时返回空串。"""
    text = manager.index_text()
    if not text:
        return ""
    return f"## Long-term Memory Index\n{text}"


def _keyword_match(query: str, memories: list[Memory], limit: int) -> list[Memory]:
    """降级方案：query 里的词出现在 name/description 里即匹配。"""
    tokens = re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", query.lower())
    if not tokens:
        return []
    scored: list[tuple[int, Memory]] = []
    for mem in memories:
        hay = f"{mem.name} {mem.description}".lower()
        score = sum(1 for t in tokens if t in hay)
        if score > 0:
            scored.append((score, mem))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]


def select_relevant(
    llm: Any, query: str, memories: list[Memory], limit: int = MAX_INJECTED
) -> list[str]:
    """side-query：让 LLM 从记忆清单里选相关的 name。失败返回空列表。"""
    if not memories:
        return []
    catalog = "\n".join(f"- {m.name}: {m.description}" for m in memories)
    user_msg = (
        f"User message: {query}\n\n"
        f"Available memories:\n{catalog}\n\n"
        f"Select relevant memory names as JSON array:"
    )
    try:
        response = llm.create(_SELECT_SYSTEM, [{"role": "user", "content": user_msg}], [])
        text = "\n".join(
            b.text for b in response.content
            if getattr(b, "type", None) == "text" and b.text
        )
        m = _JSON_ARRAY_RE.search(text)
        if not m:
            return []
        names = json.loads(m.group(0))
        if isinstance(names, list):
            return [str(n) for n in names][:limit]
    except Exception:
        pass
    return []


def inject_relevant(
    llm: Any,
    user_msg: dict[str, Any],
    manager: MemoryManager,
    limit: int = MAX_INJECTED,
) -> dict[str, Any]:
    """路径二：把相关记忆正文注入当前 user message。原地修改并返回。

    side-query 失败时降级关键词匹配；都没命中则不注入。
    """
    query = str(user_msg.get("content", ""))
    memories = manager.list_memories()
    if not memories:
        return user_msg

    names = select_relevant(llm, query, memories, limit)
    if not names:
        # 降级：关键词匹配
        matched = _keyword_match(query, memories, limit)
        chosen = [m.name for m in matched]
    else:
        name_set = set(names)
        chosen = [m.name for m in memories if m.name in name_set][:limit]

    if not chosen:
        return user_msg

    blocks = []
    for name in chosen:
        mem = manager.read(name)
        if mem is not None:
            blocks.append(f"### Memory: {mem.name}\n{mem.content}")

    if not blocks:
        return user_msg

    injected = "\n\n".join(blocks)
    original = user_msg.get("content", "")
    user_msg["content"] = (
        f"{original}\n\n---\nRelevant memories for this turn:\n{injected}"
    )
    return user_msg
