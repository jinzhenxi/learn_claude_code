"""客户端层：ClaudeClient 封装模型调用，核心方法 agent_loop。"""

import os
from typing import Any

from anthropic import Anthropic

from hooks import HookEvent


class ClaudeClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_id: str,
        registry,
        hooks,
        todos,
        max_tokens: int = 8000,
    ) -> None:
        # 显式传参，避免 ANTHROPIC_AUTH_TOKEN 等环境变量干扰
        self.client = Anthropic(base_url=base_url, api_key=api_key)
        self.model_id = model_id
        self.registry = registry
        self.hooks = hooks
        self.todos = todos
        self.max_tokens = max_tokens
        self.system = (
            f"You are a coding agent at {os.getcwd()}. "
            "Use tools to solve tasks. Act, don't explain. "
            "Before starting any multi-step task, use todo_write to plan your "
            "steps, and update status as you go. "
            "Every tool call passes through hooks: if a tool returns an "
            "error, fix the arguments and retry; if a hook blocks the call, "
            "do not repeat the action, choose another approach."
        )

    def agent_loop(self, query: str, messages: list[dict[str, Any]]) -> None:
        """循环：请求模型 -> 执行工具 -> 回填结果，直到模型不再调工具。"""
        # 用户输入入列前先触发 UserPromptSubmit
        self.hooks.trigger(HookEvent.USER_PROMPT_SUBMIT, query)
        messages.append({"role": "user", "content": query})

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
            # 没有工具调用即为本轮最终答复，触发 Stop 后结束
            if not tool_calls:
                self.hooks.trigger(HookEvent.STOP, messages)
                return

            results = [self._invoke_tool(block) for block in tool_calls]
            # 本轮结束：是否提醒由 TodoManager 按自己的闲置计数决定
            reminder = self.todos.advance_round()
            if reminder is not None:
                results.append({"type": "text", "text": reminder})
            messages.append({"role": "user", "content": results})

    def _invoke_tool(self, block: Any) -> dict[str, Any]:
        """执行前过 PreToolUse、执行后过 PostToolUse；阻断/失败都回传。"""
        try:
            tool = self.registry.get(block.name)
        except KeyError:
            return self._tool_result(
                block.id, f"Error: unknown tool '{block.name}'", True
            )

        print(f"\033[33m{tool.preview(block.input)}\033[0m")

        # 是否阻断完全由已注册的 hook 决定，循环不认识任何具体检查
        deny_reason = self.hooks.trigger(HookEvent.PRE_TOOL_USE, block)
        if deny_reason is not None:
            # 工具未执行，阻断原因原样回喂给模型
            print(f"\033[31m[blocked] {deny_reason}\033[0m")
            return self._tool_result(block.id, deny_reason, True)

        result = tool.run(**block.input)
        # PostToolUse 为观测点，结果不影响流程
        self.hooks.trigger(HookEvent.POST_TOOL_USE, block, result.content)
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
