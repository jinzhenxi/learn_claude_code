"""组装入口：主 ToolManager 内嵌一个只含基础工具的子 ToolManager。"""

from typing import Any

from .bash_tool import BashTool
from .compact_tool import CompactTool
from .edit_file_tool import EditFileTool
from .glob_tool import GlobTool
from .load_skill_tool import LoadSkillTool
from .read_file_tool import ReadFileTool
from .task_tool import TaskTool
from .todo_write_tool import TodoWriteTool
from .tool_manager import ToolManager
from .write_file_tool import WriteFileTool


def _base_tools():
    # 主/子 Agent 共享同一批实例，副作用都落在同一个 WORKDIR
    return [BashTool(), ReadFileTool(), WriteFileTool(), EditFileTool(), GlobTool()]


def build_tool_manager(
    todos: Any, llm: Any, hooks: Any, skills: Any, compactor: Any,
    fallback_model_id: str | None = None, task_manager: Any = None,
) -> ToolManager:
    # task12：持久任务系统（.tasks/）；主/子 Agent 共享，靠 owner + 锁防重复认领
    if task_manager is None:
        from task import TaskManager
        task_manager = TaskManager()
    from task import build_task_tools
    task_tools = build_task_tools(task_manager)

    base_tools = _base_tools()

    # 子管理器：基础五工具 + 只读技能加载 + 压缩 + 任务认领；禁止递归、不共享待办
    sub_manager = ToolManager()
    for tool in base_tools:
        sub_manager.register(tool)
    sub_manager.register(LoadSkillTool(skills))
    sub_manager.register(CompactTool(compactor))
    for tool in task_tools:
        sub_manager.register(tool)

    # 主管理器：在子能力之上挂 todo_write 与 task（spawner）
    main_manager = ToolManager()
    for tool in base_tools:
        main_manager.register(tool)
    main_manager.register(LoadSkillTool(skills))
    main_manager.register(CompactTool(compactor))
    for tool in task_tools:
        main_manager.register(tool)
    main_manager.register(TodoWriteTool(todos))
    # TaskTool 最后注册：它依赖子管理器，但子管理器永不包含它
    main_manager.register(
        TaskTool(llm, hooks, sub_manager, skills, compactor, fallback_model_id)
    )
    return main_manager
