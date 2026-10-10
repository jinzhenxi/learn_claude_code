"""工作区路径锚点：相对路径都解析到 WORKDIR；是否越界由权限层裁决。"""

from pathlib import Path

WORKDIR = Path.cwd().resolve()


def resolve_path(p: str) -> Path:
    """相对路径锚定 WORKDIR 并规范化；边界裁决归权限层，工具不自行拦截。"""
    return (WORKDIR / p).resolve()
