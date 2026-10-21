"""System prompt 管理：分段定义 + 按需组装 + 上下文缓存。

Agent 通过 PromptManager.get_system_prompt(build_context(...)) 获取 prompt，
循环本身不认识 prompt 的具体内容。
"""

from .builder import PromptManager, assemble_system_prompt
from .context import build_context

__all__ = ["PromptManager", "assemble_system_prompt", "build_context"]
