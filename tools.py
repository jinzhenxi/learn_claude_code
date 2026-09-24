"""工具层：Tool 抽象基类、BashTool 实现与 ToolRegistry 注册表。"""

import subprocess
from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """所有工具的统一接口；新增工具只需继承并注册，client 无需改动。"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """工具入参的 JSON Schema。"""

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """执行工具，返回给模型的文本结果。"""

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema(),
        }

    def preview(self, tool_input: dict[str, Any]) -> str:
        """终端中展示本次调用的摘要，默认打印原始入参。"""
        return f"{self.name} {tool_input}"


class BashTool(Tool):
    name = "bash"
    description = "Run a shell command."

    DANGEROUS = ("rm -rf /", "sudo", "shutdown", "reboot", "> /dev/")
    TIMEOUT = 120
    MAX_OUTPUT = 50000

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        }

    def execute(self, command: str) -> str:
        # 命中危险片段直接拦截，不进入子进程
        if any(d in command for d in self.DANGEROUS):
            return "Error: Dangerous command blocked"
        try:
            r = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.TIMEOUT,
            )
            out = (r.stdout + r.stderr).strip()
            return out[: self.MAX_OUTPUT] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Timeout ({self.TIMEOUT}s)"
        except (FileNotFoundError, OSError) as e:
            return f"Error: {e}"

    def preview(self, tool_input: dict[str, Any]) -> str:
        return f"$ {tool_input.get('command', '')}"


class ToolRegistry:
    """按名字注册/查找工具，执行分发完全替代 if-else。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        if not tool.name:
            raise ValueError("Tool.name must not be empty")
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Unknown tool: {name}") from None

    def definitions(self) -> list[dict[str, Any]]:
        return [tool.definition() for tool in self._tools.values()]
