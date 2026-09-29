"""客户端层：ClaudeClient 封装模型调用，核心方法 agent_loop。"""

import os
from typing import Any

from anthropic import Anthropic


class ClaudeClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        registry,
        permission,
        max_tokens: int = 8000,
    ) -> None:
        # 显式传参，避免 ANTHROPIC_AUTH_TOKEN 等环境变量干扰
        self.client = Anthropic(base_url=base_url, api_key=api_key)
        self.model_id = model_id
        self.registry = registry
        self.permission = permission
        self.max_tokens = max_tokens
        self.system = (
            f"You are a coding agent at {os.getcwd()}. "
            "Use tools to solve tasks. Act, don't explain. "
            "Every tool call passes a permission check: if a tool returns an "
            "error, fix the arguments and retry; if permission is denied, do "
            "not repeat the action, choose another approach."
        )

    def agent_loop(self, messages: list[dict[str, Any]]) -> None:
        """循环：请求模型 -> 执行工具 -> 回填结果，直到模型不再调工具。"""
        while True:
            response = self.client.messages.create(
                model=self.model_id,
                system=self.system,
                messages=messages,
                tools=self.registry.definitions(),
                max_tokens=self.max_tokens,
            )

            messages.append({"role": "assistant", "content": response.content})

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            # 没有工具调用即为本轮最终答复，结束循环
            if not tool_calls:
                return

            results = [self._invoke_tool(block) for block in tool_calls]
            messages.append({"role": "user", "content": results})

    def _invoke_tool(self, block: Any) -> dict[str, Any]:
        """权限通过才执行；拒绝/失败都变成可回传的 tool_result。"""
        try:
            tool = self.registry.get(block.name)
        except KeyError:
            return self._tool_result(
                block.id, f"Error: unknown tool '{block.name}'", True
            )

        print(f"\033[33m{tool.preview(block.input)}\033[0m")

        decision = self.permission.check(block.name, block.input)
        if not decision.allowed:
            # 被权限拦截：工具未执行，原因回喂给模型
            print(f"\033[31m[denied] {decision.reason}\033[0m")
            return self._tool_result(
                block.id, f"Permission denied: {decision.reason}", True
            )

        result = tool.run(**block.input)
        color = "\033[31m" if result.is_error else "\033[32m"
        print(f"{color}{result.content[:200]}\033[0m")
        return self._tool_result(block.id, result.content, result.is_error)

    @staticmethod
    def _tool_result(tool_use_id: str, content: str, is_error: bool) -> dict[str, Any]:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
            "is_error": is_error,
        }
