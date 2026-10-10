"""edit_file 工具：精确文本替换一次。"""

from .base_tool import BaseTool
from .paths import resolve_path


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Replace exact text in a file once."

    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        }

    def execute(self, path: str, old_text: str, new_text: str) -> str:
        file_path = resolve_path(path)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            raise ValueError(f"text not found in {path}")
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"

    def preview(self, tool_input) -> str:
        return f"edit {tool_input.get('path', '')}"
