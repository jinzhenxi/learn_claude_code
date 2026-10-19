"""持久记忆系统：文件系统存储 + 两条注入路径 + 每轮结束提取与整理。"""

from .store import Memory, MemoryManager
from .inject import system_index_text, inject_relevant
from .extract import extract_and_save, consolidate_memories

__all__ = [
    "MemoryManager", "Memory",
    "system_index_text", "inject_relevant",
    "extract_and_save", "consolidate_memories",
]
