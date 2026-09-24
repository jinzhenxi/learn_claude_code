"""入口：组装配置、工具与客户端，启动交互式 REPL。"""

try:
    import readline

    # #143 UTF-8 backspace fix for macOS libedit
    readline.parse_and_bind("set bind-tty-special-chars off")
    readline.parse_and_bind("set input-meta on")
    readline.parse_and_bind("set output-meta on")
    readline.parse_and_bind("set convert-meta off")
except ImportError:
    pass

from client import ClaudeClient
from config import Config
from tools import BashTool, ToolRegistry


def main() -> None:
    config = Config.load()
    registry = ToolRegistry().register(BashTool())
    client = ClaudeClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model_id=config.model_id,
        registry=registry,
    )

    print("s01: Agent Loop")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history = []
    while True:
        try:
            # \001/\002 告知 Readline 中间的 ANSI 转义显示宽度为 0
            query = input("\001\033[36m\002s01 >> \001\033[0m\002")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append({"role": "user", "content": query})
        client.agent_loop(history)

        # 打印模型本轮最终答复中的 text 块
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if getattr(block, "type", None) == "text":
                    print(block.text)
        print()


if __name__ == "__main__":
    main()
