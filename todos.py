"""任务状态层：TodoManager 持有并校验模型自己维护的进度列表。

- 列表整体替换：todo_write 是唯一写入点，不做增量编辑。
- 先校验后替换：任何一项不合法都抛 ValueError，原状态保持不变。
- 提醒策略内聚于此：连续 N 轮没有更新，advance_round() 返回提醒文本；
  循环不认识 todo_write，也不数轮次，只在每轮结束时问一次。

运作流程
========

写入流程（模型调用 todo_write 工具触发）::

    模型传入 raw（list 或 JSON 字符串）
            |
            v
    +--------------------+
    | TodoManager.update |
    +---------+----------+
              |
              v
    coerce_list(raw)  ── 非 list / 解析失败 ──> raise ValueError
              |
              v
    len(todos) <= MAX_TODOS ?  ── 否 ──> raise ValueError
              | 是
              v
    逐项解析 entry:
      content = entry["content"].strip()
      status  = entry["status"].lower()  (默认 pending)
      TodoItem(content, status)  ── 空内容 / 非法状态 ──> raise ValueError(todos[i] ...)
              |
              v
    in_progress 数量 <= 1 ?  ── 否 ──> raise ValueError
              | 是
              v
    全部合法：
      self._items = parsed        # 整体替换
      self._idle_rounds = 0       # 刚更新，闲置归零
      return self.render()        # 返回带标记的可读文本

    注：任一环节抛错时 self._items 不被修改，原状态保持不变。

轮次结束流程（主循环每轮末尾调用一次）::

    advance_round()
        |
        v
    self._idle_rounds += 1
        |
        v
    _idle_rounds < REMINDER_INTERVAL ?
        | 是                          | 否
        v                             v
    return None                 _idle_rounds = 0
                                return REMINDER_TEXT
                                （由主循环注入到下一轮提示中，
                                 催促模型更新 todos）

状态标记（render 输出）::

    [ ]  pending        未开始
    [>]  in_progress    进行中（同时最多一个）
    [x]  completed      已完成
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
