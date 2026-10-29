"""后台任务判定策略：显式请求优先，启发式兜底。"""

# 启发式关键词：命令中出现任一即视为可能耗时 > 30s
SLOW_KEYWORDS = (
    "install", "build", "test", "deploy", "compile",
    "docker build", "pip install", "npm install",
    "cargo build", "pytest", "make",
)


def is_slow_operation(tool_name: str, tool_input: dict) -> bool:
    """兜底启发式：仅 bash 工具参与判定。"""
    if tool_name != "bash":
        return False
    cmd = tool_input.get("command", "").lower()
    return any(kw in cmd for kw in SLOW_KEYWORDS)


def should_run_background(tool_name: str, tool_input: dict) -> bool:
    """模型显式 run_in_background=True 优先；否则走启发式。"""
    if tool_input.get("run_in_background"):
        return True
    return is_slow_operation(tool_name, tool_input)
