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
            "properties": {
                "command": {"type": "string"},
                "run_in_background": {
                    "type": "boolean",
                    "description": "Run the command in a background thread; "
                                   "returns immediately with a task ID.",
                },
            },
            "required": ["command"],
        }

    def execute(self, command: str, run_in_background: bool = False) -> str:
        # run_in_background 由后台管理器的 PRE_TOOL_USE hook 处理，
        # 工具本身始终同步执行；该参数仅用于 schema 声明。
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
        prefix = "[bg] " if tool_input.get("run_in_background") else ""
        return f"{prefix}$ {tool_input.get('command', '')}"
