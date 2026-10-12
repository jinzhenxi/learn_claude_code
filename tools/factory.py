"""组装入口：主 ToolManager 内嵌一个只含基础工具的子 ToolManager。"""

from typing import Any

from .bash_tool import BashTool
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
    todos: Any, llm: Any, hooks: Any, skills: Any
) -> ToolManager:
    base_tools = _base_tools()

    # 子管理器：基础五工具 + 只读技能加载；禁止递归、不共享待办
    sub_manager = ToolManager()
    for tool in base_tools:
        sub_manager.register(tool)
    sub_manager.register(LoadSkillTool(skills))

    # 主管理器：在子能力之上挂 todo_write 与 task
    main_manager = ToolManager()
    for tool in base_tools:
        main_manager.register(tool)
    main_manager.register(LoadSkillTool(skills))
    main_manager.register(TodoWriteTool(todos))
    # TaskTool 最后注册：它依赖子管理器，但子管理器永不包含它
    main_manager.register(TaskTool(llm, hooks, sub_manager, skills))
    return main_manager
