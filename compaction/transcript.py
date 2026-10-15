"""Transcript：压缩前把完整对话以 JSONL 落盘，保留可恢复记录。"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .blocks import to_jsonable
from .paths import MAX_TRANSCRIPT_FILES, TRANSCRIPT_DIR, WORKDIR, rotate

# budget 占位符里的相对路径，用于还原原文
_PERSIST_RE = re.compile(r"\[Large output persisted to (\.tool_outputs/[^\s)]+)")


def _restore_persisted(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """transcript 专用：把 budget 落盘的占位符还原为原文。

    micro 折叠的结果（无对应文件）保持占位符不变；budget 落盘的从
    .tool_outputs/ 读回。仅作用于 transcript 的副本，不污染活跃 messages。
    """
    restored = []
    for message in messages:
        if not isinstance(message.get("content"), list):
            restored.append(message)
            continue
        new_blocks = []
        for block in message["content"]:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_result"
                and isinstance(block.get("content"), str)
            ):
                m = _PERSIST_RE.search(block["content"])
                if m:
                    rel = m.group(1)
                    full = WORKDIR / rel
                    if full.exists():
                        block = {**block, "content": full.read_text(encoding="utf-8")}
            new_blocks.append(block)
        restored.append({**message, "content": new_blocks})
    return restored


def write_transcript(messages: list[dict[str, Any]], tag: str = "compact") -> str:
    """每条消息一行 JSON，返回相对工作区的路径。budget 落盘内容会还原。"""
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = TRANSCRIPT_DIR / f"{stamp}-{tag}-{uuid.uuid4().hex[:8]}.jsonl"
    snapshot = _restore_persisted(messages)
    with path.open("w", encoding="utf-8") as f:
        for message in snapshot:
            f.write(json.dumps(to_jsonable(message), ensure_ascii=False))
            f.write("\n")
    rotate(TRANSCRIPT_DIR, MAX_TRANSCRIPT_FILES)
    return str(path.relative_to(TRANSCRIPT_DIR.parent))
