"""System prompt 分段定义。

每个 section 独立维护：改 tools 不影响 identity，加 memory 不动 workspace。
assemble_system_prompt 按真实状态决定加载哪些，不是全部硬塞。
"""

# 身份：主/子 Agent 不同
IDENTITY_MAIN = (
    "You are a coding agent. Use tools to solve tasks. Act, don't explain."
)

IDENTITY_SUB = (
    "You are a subagent spawned to complete one delegated subtask. "
    "Work autonomously with the available tools; file changes persist in the "
    "shared workspace. When finished, reply with only the final conclusion."
)

# 工具使用约定（所有 agent 共享）
TOOLS_GUIDANCE = (
    "Every tool call passes through hooks: if a tool returns an error, fix the "
    "arguments and retry; if a hook blocks the call, do not repeat the action, "
    "choose another approach."
)

# 任务规划提示（仅主 Agent 且注册了 todo_write 时加载）
TODO_HINT = (
    "Before starting any multi-step task, use todo_write to plan your steps, "
    "and update status as you go."
)

# 子任务委派提示（仅主 Agent 且注册了 task 时加载）
TASK_HINT = (
    "Delegate self-contained subtasks to the task tool; it returns only the "
    "subagent's final conclusion."
)

# 记忆索引的标题前缀（正文由 memory 层提供）
MEMORY_HEADER = "## Long-term Memory Index"
