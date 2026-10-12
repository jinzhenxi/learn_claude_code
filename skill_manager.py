"""技能层：启动期扫描 skills/，把可用技能目录注入 system prompt。

与 tool/subagent 的边界：skill 只是"按需加载的知识文档"，没有可执行
契约。注册表以 frontmatter 的 name 为键，加载走字典查找而非文件路径，
天然不存在路径遍历。
"""

import re
from dataclasses import dataclass
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
SKILL_FILE = "SKILL.md"

# name 只允许小写字母/数字/-/_，注册表键始终受控
_VALID_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# 随技能附带、可用现有 file/bash 工具进一步访问的子目录
_BUNDLED_DIRS = ("references", "scripts", "assets")


def _parse_frontmatter(raw: str, source: Path) -> tuple[dict[str, str], str]:
    """解析极简 YAML frontmatter（仅 key: value），不依赖 PyYAML。"""
    # 兼容首行即 --- 或带 BOM 的情况
    if not raw.startswith("---"):
        raise ValueError(f"{source}: missing frontmatter")
    lines = raw.splitlines()
    if lines[0].strip() != "---":
        raise ValueError(f"{source}: frontmatter must start with '---'")

    meta: dict[str, str] = {}
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
        line = lines[index]
        if ":" not in line:
            raise ValueError(f"{source}: frontmatter line must be 'key: value'")
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip("'\"")
    if end is None:
        raise ValueError(f"{source}: frontmatter must end with '---'")

    body = "\n".join(lines[end + 1:]).lstrip("\n")
    return meta, body


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path  # SKILL.md 的绝对路径


class SkillManager:
    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self.skills_dir = skills_dir
        self._skills: dict[str, Skill] = {}

    @classmethod
    def scan(cls, skills_dir: Path = SKILLS_DIR) -> "SkillManager":
        """启动时调用：枚举每个技能子目录的 SKILL.md 并建注册表。"""
        manager = cls(skills_dir)
        if not skills_dir.is_dir():
            return manager
        for skill_md in sorted(skills_dir.glob(f"*/{SKILL_FILE}")):
            meta, _ = _parse_frontmatter(skill_md.read_text(encoding="utf-8"),
                                         skill_md)
            name = meta.get("name", "")
            description = meta.get("description", "")
            if not _VALID_NAME.match(name):
                raise ValueError(
                    f"{skill_md}: invalid skill name '{name}'"
                )
            if not description:
                raise ValueError(f"{skill_md}: missing description")
            if name in manager._skills:
                raise ValueError(f"duplicate skill name '{name}'")
            manager._skills[name] = Skill(name, description, skill_md)
        return manager

    def catalog(self) -> str:
        """生成技能目录文本，拼进 system prompt，每轮可见、零额外调用。"""
        if not self._skills:
            return ""
        lines = ["Available skills (load one with the load_skill tool):"]
        lines.extend(f"- {s.name}: {s.description}"
                     for s in self._skills.values())
        return "\n".join(lines)

    def load(self, name: str) -> str:
        """按注册表名查找并返回 SKILL.md 正文；未知技能抛 KeyError。"""
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(f"Unknown skill: {name}")
        _, body = _parse_frontmatter(
            skill.path.read_text(encoding="utf-8"), skill.path
        )
        bundled = self._bundled_files(skill.path.parent)
        if bundled:
            body += "\n\nBundled files (access with read_file / bash / glob):\n"
            body += "\n".join(f"- {rel}" for rel in bundled)
        return body

    @staticmethod
    def _bundled_files(skill_dir: Path) -> list[str]:
        files: list[str] = []
        for folder in _BUNDLED_DIRS:
            base = skill_dir / folder
            if not base.is_dir():
                continue
            files.extend(
                str(p.relative_to(skill_dir))
                for p in sorted(base.rglob("*"))
                if p.is_file()
            )
        return files
