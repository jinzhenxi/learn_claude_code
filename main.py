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
from background import BackgroundTaskManager
from client import ClaudeClient
from compaction import ContextCompactor
from config import Config
from hooks import HookEvent, build_default_hooks
from memory import MemoryManager, extract_and_save, inject_relevant
from permission import build_default_permission
from skill_manager import SkillManager
from task import TaskManager
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
    # 启动时扫描 skills/，注册表就绪后目录即可注入 system prompt
    skills = SkillManager.scan()
    # 上下文压缩作为 PreLLMCall mutator 挂进注册表，循环零感知；顺序即加工顺序
    compactor = ContextCompactor(llm)
    hooks.register_mutator(HookEvent.PRE_LLM_CALL, compactor.prepare)
    hooks.register_mutator(HookEvent.PRE_LLM_CALL, compactor.maybe_summarize)
    # task09：持久记忆
    memory = MemoryManager()
    # 路径二：用户请求开始时 side-query 选相关记忆注入当前 user turn
    hooks.register_mutator(
        HookEvent.USER_PROMPT_SUBMIT,
        lambda msg: inject_relevant(llm, msg, memory),
    )
    # 写入：每轮结束（STOP）后提取稳定偏好/事实，持久化为记忆
    hooks.register(
        HookEvent.STOP,
        lambda messages: (extract_and_save(llm, messages, memory), None)[1],
    )
    # task12：持久任务系统（.tasks/，blockedBy 依赖与认领状态机）
    task_manager = TaskManager()
    registry = build_tool_manager(
        todos, llm, hooks, skills, compactor,
        config.fallback_model_id, task_manager,
    )
    # task13：后台任务——耗时命令丢 daemon 线程，结果以通知回收，主循环零感知
    bg_manager = BackgroundTaskManager(registry)
    bg_manager.register_hooks(hooks)
    agent = MainAgent(
        llm, registry, hooks, todos, skills, compactor, memory,
        config.fallback_model_id,
    )

    print("s13: Background Tasks")
    print("Enter a question, press Enter to send. Type q to quit.\n")

    history = []
    while True:
        try:
            # \001/\002 告知 Readline 中间的 ANSI 转义显示宽度为 0
            query = input("\001\033[36m\002s13 >> \001\033[0m\002")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        user_msg = {"role": "user", "content": query}
        # observer 日志 + mutator 注入相关记忆
        hooks.trigger(HookEvent.USER_PROMPT_SUBMIT, user_msg)
        user_msg = hooks.apply(HookEvent.USER_PROMPT_SUBMIT, user_msg)
        history.append(user_msg)
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
