"""glob 工具：按通配模式查找文件，** 表示递归。"""

from .base_tool import BaseTool
from .paths import WORKDIR


class GlobTool(BaseTool):
    name = "glob"
    description = "Find files matching a glob pattern; ** matches recursively."

    MAX_MATCHES = 200

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        }

    def execute(self, pattern: str) -> str:
        # 去重并剔除经符号链接逃逸出工作区的路径
        matches = sorted({
            str(m.relative_to(WORKDIR))
            for m in WORKDIR.glob(pattern)
            if m.resolve().is_relative_to(WORKDIR)
        })
        shown = matches[: self.MAX_MATCHES]
        if len(matches) > self.MAX_MATCHES:
            shown.append("... (more matches omitted; narrow the pattern)")
        return "\n".join(shown) if shown else "(no matches)"

    def preview(self, tool_input) -> str:
        return f"glob {tool_input.get('pattern', '')}"
