"""权限层：工具执行前固定经过三道闸门。

顺序固定：Gate1 硬拒绝（命中即拒，不询问）
          Gate2 规则匹配（命中则转 Gate3）
          Gate3 用户批准（用户决定 allow / deny）
都没命中则放行。
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from tools import WORKDIR, resolve_path


class Verdict(Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str | None = None

    @property
    def allowed(self) -> bool:
        return self.verdict is Verdict.ALLOW


# -- Gate 1 / Gate 2 的统一接口 --

class Gate(ABC):
    @abstractmethod
    def inspect(self, tool_name: str, tool_input: dict[str, Any]) -> str | None:
        """命中返回原因，未命中返回 None。"""


# -- Gate 1: hard deny list --

class DenyListGate(Gate):
    PATTERNS = (
        "rm -rf /", "sudo", "shutdown", "reboot",
        "mkfs", "dd if=", "> /dev/sda",
    )

    def inspect(self, tool_name: str, tool_input: dict[str, Any]) -> str | None:
        if tool_name != "bash":
            return None
        command = tool_input.get("command", "")
        for pattern in self.PATTERNS:
            if pattern in command:
                return f"Blocked: '{pattern}' is on the deny list"
        return None


# -- Gate 2: pluggable rules --

class PermissionRule(ABC):
    """单条上下文规则；适用工具与判定方式各自封装，新增规则无需改 Gate。"""

    tools: frozenset[str] = frozenset()
    reason: str = ""

    def applies_to(self, tool_name: str) -> bool:
        return tool_name in self.tools

    @abstractmethod
    def violated_by(self, tool_input: dict[str, Any]) -> bool:
        """命中表示该操作需要用户确认。"""


class OutsideWorkspaceRule(PermissionRule):
    tools = frozenset({"read_file", "write_file", "edit_file"})
    reason = "Accessing path outside workspace"

    def violated_by(self, tool_input: dict[str, Any]) -> bool:
        path = tool_input.get("path")
        if not path:
            return False
        return not resolve_path(path).is_relative_to(WORKDIR)


DESTRUCTIVE_WORD = re.compile(
    r"(?i)(?:^|[;&|()\n])\s*(?:rm|del)(?=\s|$|[;&|()])"
)


class DestructiveCommandRule(PermissionRule):
    tools = frozenset({"bash"})
    reason = "Potentially destructive command"
    KEYWORDS = ("rm ", "> /etc/", "chmod 777")

    def violated_by(self, tool_input: dict[str, Any]) -> bool:
        command = tool_input.get("command", "")
        return bool(DESTRUCTIVE_WORD.search(command)) or any(
            kw in command for kw in self.KEYWORDS
        )


class RuleGate(Gate):
    def __init__(self, rules: list[PermissionRule]) -> None:
        self.rules = rules

    def inspect(self, tool_name: str, tool_input: dict[str, Any]) -> str | None:
        for rule in self.rules:
            if rule.applies_to(tool_name) and rule.violated_by(tool_input):
                return rule.reason
        return None


# -- Gate 3: user approval --

class Approver(ABC):
    @abstractmethod
    def confirm(self, tool_name: str, tool_input: dict[str, Any], reason: str) -> bool:
        """必须真实等待用户决定，禁止默认放行。"""


def _summarize(tool_input: dict[str, Any], limit: int = 80) -> dict[str, Any]:
    # 长文本（如 write_file 的 content）截断后再展示
    out = {}
    for k, v in tool_input.items():
        v = str(v)
        out[k] = v if len(v) <= limit else v[:limit] + "..."
    return out


class ConsoleApprover(Approver):
    def confirm(self, tool_name, tool_input, reason) -> bool:
        print(f"\n\033[33m[permission] {reason}\033[0m")
        print(f"   Tool: {tool_name}({_summarize(tool_input)})")
        choice = input("   Allow? [y/N] ").strip().lower()
        return choice in ("y", "yes")


# -- Pipeline: three gates chained --

class Permission:
    def __init__(
        self,
        deny_gate: Gate,
        rule_gate: Gate,
        approver: Approver,
    ) -> None:
        self.deny_gate = deny_gate
        self.rule_gate = rule_gate
        self.approver = approver

    def check(self, tool_name: str, tool_input: dict[str, Any]) -> Decision:
        # Gate 1 命中：立即拒绝，不再询问
        hard_reason = self.deny_gate.inspect(tool_name, tool_input)
        if hard_reason:
            return Decision(Verdict.DENY, hard_reason)

        # Gate 2 未命中：放行
        soft_reason = self.rule_gate.inspect(tool_name, tool_input)
        if not soft_reason:
            return Decision(Verdict.ALLOW)

        # Gate 2 命中：交给 Gate 3 由用户裁决
        if self.approver.confirm(tool_name, tool_input, soft_reason):
            return Decision(Verdict.ALLOW, soft_reason)
        return Decision(Verdict.DENY, f"{soft_reason} (user declined)")


def build_default_permission() -> Permission:
    return Permission(
        deny_gate=DenyListGate(),
        rule_gate=RuleGate([OutsideWorkspaceRule(), DestructiveCommandRule()]),
        approver=ConsoleApprover(),
    )
