"""压缩产物的落盘位置：独立锚定 cwd，不反向依赖 tools 包以免成环。"""

import re
from pathlib import Path

WORKDIR = Path.cwd().resolve()
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
TOOL_OUTPUT_DIR = WORKDIR / ".tool_outputs"

# 轮转上限：超过则按 mtime 删除最旧的，避免长时间跑无限涨盘
MAX_TRANSCRIPT_FILES = 100
MAX_TOOL_OUTPUT_FILES = 200


def safe_filename(tool_use_id: str) -> str:
    """把 tool_use_id 规整成安全文件名（去路径分隔符）。"""
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(tool_use_id))
    return name[:80] or "output"


def rotate(directory: Path, max_files: int) -> None:
    """保留 directory 下最近 max_files 个文件，删除最旧的。"""
    files = sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime)
    for old in files[:-max_files] if len(files) > max_files else []:
        try:
            old.unlink()
        except OSError:
            pass
