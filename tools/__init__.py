"""工具层：BaseTool 基类、ToolManager 管理器与各独立工具。

保留稳定聚合面：调用方统一从 tools 导入，WORKDIR/resolve_path 也从这里
重导出，permission/hooks 无需改动。
"""

from .base_tool import BaseTool, ToolResult
from .factory import build_tool_manager
from .paths import WORKDIR, resolve_path
from .tool_manager import ToolManager

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolManager",
    "build_tool_manager",
    "WORKDIR",
    "resolve_path",
]
