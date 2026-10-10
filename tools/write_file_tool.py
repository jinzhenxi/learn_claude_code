"""write_file 工具：整体写入文本文件。"""

from .base_tool import BaseTool
from .paths import resolve_path


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file."

    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        }

    def execute(self, path: str, content: str) -> str:
        file_path = resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"

    def preview(self, tool_input) -> str:
        return f"write {tool_input.get('path', '')}"
