"""bash 工具：在 WORKDIR 内执行 shell 命令。"""

import subprocess

from .base_tool import BaseTool
from .paths import WORKDIR


class BashTool(BaseTool):
    name = "bash"
    description = "Run a shell command."

    TIMEOUT = 120
    MAX_OUTPUT = 50000

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        }

    def execute(self, command: str) -> str:
        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=WORKDIR,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Timeout ({self.TIMEOUT}s)") from None
        out = (r.stdout + r.stderr).strip()
        shown = out[: self.MAX_OUTPUT] if out else "(no output)"
        # 非零退出即失败：抛出后由基类收口为带 is_error 的 ToolResult
        if r.returncode != 0:
            raise RuntimeError(f"exit {r.returncode}: {shown}")
        return shown

    def preview(self, tool_input) -> str:
        return f"$ {tool_input.get('command', '')}"
