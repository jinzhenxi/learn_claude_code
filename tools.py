"""工具层：Tool 抽象基类、各工具实现与 ToolRegistry 注册表。"""

import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 相对路径的锚点；是否允许越界由 permission 层裁决
WORKDIR = Path.cwd().resolve()


def resolve_path(p: str) -> Path:
    """相对路径锚定 WORKDIR 并规范化；边界裁决归权限层，工具不再自行拦截。"""
    return (WORKDIR / p).resolve()


@dataclass(frozen=True)
class ToolResult:
    """一次工具调用的归一化结果：永不以异常形式出现。"""

    content: str
    is_error: bool = False


class Tool(ABC):
    """所有工具的统一接口；新增工具只需继承并注册，client 无需改动。"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """工具入参的 JSON Schema。"""

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """成功路径：返回文本结果；失败直接 raise，无需自行 try/except。"""

    def run(self, **kwargs: Any) -> ToolResult:
        # 模板方法：唯一的异常收口点，保证任何工具都不会把异常抛给 client
        try:
            return ToolResult(content=self.execute(**kwargs))
        except Exception as e:
            return ToolResult(
                content=f"Error: {type(e).__name__}: {e}",
                is_error=True,
            )

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

    TIMEOUT = 120
    MAX_OUTPUT = 50000

    def input_schema(self) -> dict[str, Any]:
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
        return out[: self.MAX_OUTPUT] if out else "(no output)"

    def preview(self, tool_input: dict[str, Any]) -> str:
        return f"$ {tool_input.get('command', '')}"


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read file contents."

    def input_schema(self) -> dict[str, Any]:
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

    def preview(self, tool_input: dict[str, Any]) -> str:
        return f"read {tool_input.get('path', '')}"


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file."

    def input_schema(self) -> dict[str, Any]:
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

    def preview(self, tool_input: dict[str, Any]) -> str:
        return f"write {tool_input.get('path', '')}"


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace exact text in a file once."

    def input_schema(self) -> dict[str, Any]:
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

    def preview(self, tool_input: dict[str, Any]) -> str:
        return f"edit {tool_input.get('path', '')}"


class GlobTool(Tool):
    name = "glob"
    description = "Find files matching a glob pattern; ** matches recursively."

    MAX_MATCHES = 200

    def input_schema(self) -> dict[str, Any]:
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

    def preview(self, tool_input: dict[str, Any]) -> str:
        return f"glob {tool_input.get('pattern', '')}"


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


def build_default_registry() -> ToolRegistry:
    """内置工具清单；新增工具后在这里加一行即完成注册。"""
    registry = ToolRegistry()
    for tool in (
        BashTool(),
        ReadFileTool(),
        WriteFileTool(),
        EditFileTool(),
        GlobTool(),
    ):
        registry.register(tool)
    return registry
