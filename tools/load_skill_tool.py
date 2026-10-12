"""load_skill 工具：按名加载技能正文，知识以 tool_result 注入。"""

from typing import TYPE_CHECKING

from .base_tool import BaseTool

if TYPE_CHECKING:
    from skill_manager import SkillManager


class LoadSkillTool(BaseTool):
    name = "load_skill"
    description = (
        "Load a skill's SKILL.md by name from the available skills catalog."
    )

    def __init__(self, manager: "SkillManager") -> None:
        self.manager = manager

    def input_schema(self):
        return {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }

    def execute(self, name: str) -> str:
        # 注册表字典查找，不接触文件路径
        return self.manager.load(name)

    def preview(self, tool_input) -> str:
        return f"load_skill {tool_input.get('name', '')}"
