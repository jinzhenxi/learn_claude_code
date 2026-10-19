"""持久记忆存储：.memory/ 下每个记忆一个 .md 文件，YAML frontmatter 记元数据。

MEMORY.md 是索引，一行一个链接，常驻 system prompt（可被 prompt cache 缓存）。
记忆正文按需注入到当前 user turn，不破坏 cache。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORKDIR = Path.cwd().resolve()
MEMORY_DIR = WORKDIR / ".memory"

# frontmatter 解析
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class Memory:
    name: str
    description: str
    type: str  # user / project / fact
    content: str
    path: Path

    @property
    def link_line(self) -> str:
        """MEMORY.md 里的一行索引。"""
        rel = self.path.relative_to(self.path.parent.parent)
        return f"- [{self.name}]({rel.as_posix()}) — {self.description}"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    body = text[m.end():]
    return meta, body


class MemoryManager:
    """记忆文件的 CRUD + 索引重建。纯文件系统，无网络。"""

    def __init__(self, memory_dir: Path = MEMORY_DIR) -> None:
        self.dir = memory_dir
        self.index_file = self.dir / "MEMORY.md"
        self.dir.mkdir(parents=True, exist_ok=True)

    # -- 读 --

    def list_memories(self) -> list[Memory]:
        memories: list[Memory] = []
        for path in sorted(self.dir.glob("*.md")):
            if path.name == "MEMORY.md":
                continue
            text = path.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(text)
            memories.append(
                Memory(
                    name=meta.get("name", path.stem),
                    description=meta.get("description", ""),
                    type=meta.get("type", "fact"),
                    content=body.strip(),
                    path=path,
                )
            )
        return memories

    def read(self, name: str) -> Memory | None:
        for mem in self.list_memories():
            if mem.name == name:
                return mem
        return None

    def index_text(self) -> str:
        """MEMORY.md 全文；空时返回空串。常驻 system prompt。"""
        if not self.index_file.exists():
            return ""
        return self.index_file.read_text(encoding="utf-8").strip()

    # -- 写 --

    def save(
        self, name: str, description: str, type_: str, content: str
    ) -> Memory:
        """写入或覆盖一个记忆文件，并重建索引。"""
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:80] or "memory"
        path = self.dir / f"{safe}.md"
        body = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"type: {type_}\n"
            f"---\n\n"
            f"{content.strip()}\n"
        )
        path.write_text(body, encoding="utf-8")
        self.rebuild_index()
        return Memory(name, description, type_, content.strip(), path)

    def delete(self, name: str) -> bool:
        mem = self.read(name)
        if mem is None:
            return False
        mem.path.unlink()
        self.rebuild_index()
        return True

    def clear(self) -> None:
        """删除所有记忆文件（不含 MEMORY.md）。"""
        for path in self.dir.glob("*.md"):
            if path.name != "MEMORY.md":
                path.unlink()

    def replace_all(self, memories: list[dict[str, str]]) -> list[str]:
        """用新记忆列表全量替换现有记忆，返回写入的 name 列表。

        用于 consolidate：先清空再批量写入，保证去重/合并/淘汰原子生效。
        """
        self.clear()
        written: list[str] = []
        for m in memories:
            name = str(m.get("name", "")).strip()
            description = str(m.get("description", "")).strip()
            type_ = str(m.get("type", "fact")).strip() or "fact"
            content = str(m.get("content", "")).strip()
            if name and description and content:
                self.save(name, description, type_, content)
                written.append(name)
        return written

    def rebuild_index(self) -> None:
        """根据 .memory/*.md 重建 MEMORY.md。"""
        lines = ["# Memory Index", ""]
        for mem in self.list_memories():
            lines.append(mem.link_line)
        self.index_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # -- 整理 --

    def deduplicate(self) -> list[str]:
        """按 description 去重（描述相同即语义重复），保留最新文件。返回被删的 name 列表。"""
        seen: dict[str, Memory] = {}
        removed: list[str] = []
        for mem in self.list_memories():
            key = mem.description
            if key in seen:
                older = seen[key]
                if mem.path.stat().st_mtime >= older.path.stat().st_mtime:
                    older.path.unlink()
                    removed.append(older.name)
                    seen[key] = mem
                else:
                    mem.path.unlink()
                    removed.append(mem.name)
            else:
                seen[key] = mem
        if removed:
            self.rebuild_index()
        return removed
