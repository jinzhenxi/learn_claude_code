"""read_file 工具：读取文本文件，可按行数截断。"""

from .base_tool import BaseTool
from .paths import resolve_path


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read file contents."

    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        }

    def execute(self, path: str, limit: int | None = None) -> str:
        lines = resolve_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)

    def preview(self, tool_input) -> str:
        return f"read {tool_input.get('path', '')}"
