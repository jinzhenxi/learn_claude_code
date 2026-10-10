"""入口：组装 LLM、注册表、hooks 与主 Agent，启动交互式 REPL。"""

try:
    import readline

    # #143 UTF-8 backspace fix for macOS libedit
    readline.parse_and_bind("set bind-tty-special-chars off")
    readline.parse_and_bind("set input-meta on")
    readline.parse_and_bind("set output-meta on")
    readline.parse_and_bind("set convert-meta off")
except ImportError:
    pass

from agent import MainAgent
from client import ClaudeClient
from config import Config
from hooks import HookEvent, build_default_hooks
from permission import build_default_permission
from todos import TodoManager
from tools import build_tool_manager


def main() -> None:
    config = Config.load()
    llm = ClaudeClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model_id=config.model_id,
    )

    todos = TodoManager()
    permission = build_default_permission()
    # s03 的权限管道作为众多回调之一挂进 hook 注册表；子 Agent 复用同一份
    hooks = build_default_hooks(permission)
    registry = build_tool_manager(todos, llm, hooks)
    agent = MainAgent(llm, registry, hooks, todos)

    print("s06: Agent Loop with Subagents")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history = []
    while True:
        try:
            # \001/\002 告知 Readline 中间的 ANSI 转义显示宽度为 0
            query = input("\001\033[36m\002s06 >> \001\033[0m\002")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        hooks.trigger(HookEvent.USER_PROMPT_SUBMIT, query)
        history.append({"role": "user", "content": query})
        agent.run(history)

        # 打印模型本轮最终答复中的 text 块
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if getattr(block, "type", None) == "text":
                    print(block.text)
        print()


if __name__ == "__main__":
    main()
