"""任务状态层：TodoManager 持有并校验模型自己维护的进度列表。

- 列表整体替换：todo_write 是唯一写入点，不做增量编辑。
- 先校验后替换：任何一项不合法都抛 ValueError，原状态保持不变。
- 提醒策略内聚于此：连续 N 轮没有更新，advance_round() 返回提醒文本；
  循环不认识 todo_write，也不数轮次，只在每轮结束时问一次。
"""

import ast
import json
from dataclasses import dataclass

PENDING = "pending"
IN_PROGRESS = "in_progress"
COMPLETED = "completed"
VALID_STATUSES = frozenset({PENDING, IN_PROGRESS, COMPLETED})

MAX_TODOS = 20
REMINDER_INTERVAL = 3
REMINDER_TEXT = "<reminder>Update your todos.</reminder>"

_MARKERS = {PENDING: "[ ]", IN_PROGRESS: "[>]", COMPLETED: "[x]"}


def coerce_list(raw: object) -> list:
    """模型正常传 list；兼容 JSON / Python 字面量字符串的防御性解析。"""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            try:
                raw = ast.literal_eval(raw)
            except (SyntaxError, ValueError) as e:
                raise ValueError(
                    "todos must be a list or JSON array string"
                ) from e
    if not isinstance(raw, list):
        raise ValueError("todos must be a list")
    return raw


@dataclass(frozen=True)
class TodoItem:
    content: str
    status: str = PENDING

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("requires content")
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid status '{self.status}'")


class TodoManager:
    def __init__(self) -> None:
        self._items: list[TodoItem] = []
        self._idle_rounds = 0

    @property
    def items(self) -> list[dict[str, str]]:
        return [{"content": i.content, "status": i.status} for i in self._items]

    def update(self, raw: object) -> str:
        todos = coerce_list(raw)
        if len(todos) > MAX_TODOS:
            raise ValueError(f"Max {MAX_TODOS} todos allowed")

        parsed: list[TodoItem] = []
        for index, entry in enumerate(todos):
            if not isinstance(entry, dict):
                raise ValueError(f"todos[{index}] must be an object")
            content = str(entry.get("content", "")).strip()
            status = str(entry.get("status", PENDING)).strip().lower()
            try:
                parsed.append(TodoItem(content, status))
            except ValueError as e:
                # 带上具体下标，模型才能定位是哪一项写错了
                raise ValueError(f"todos[{index}] {e}") from None

        if sum(i.status == IN_PROGRESS for i in parsed) > 1:
            raise ValueError("Only one todo can be in_progress at a time")

        # 全部合法才替换；并视为"刚更新"，闲置计数归零
        self._items = parsed
        self._idle_rounds = 0
        return self.render()

    def advance_round(self) -> str | None:
        """一轮工具执行结束后调用；无更新满 REMINDER_INTERVAL 轮则返回提醒。"""
        self._idle_rounds += 1
        if self._idle_rounds < REMINDER_INTERVAL:
            return None
        self._idle_rounds = 0
        return REMINDER_TEXT

    def render(self) -> str:
        if not self._items:
            return "No todos."
        lines = [f"{_MARKERS[i.status]} {i.content}" for i in self._items]
        done = sum(i.status == COMPLETED for i in self._items)
        lines.append(f"\n({done}/{len(self._items)} completed)")
        return "\n".join(lines)
