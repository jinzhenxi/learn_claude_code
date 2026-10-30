"""五段式 cron 表达式匹配。

字段顺序：分钟 小时 日(月) 月 星期
DOM 与 DOW 同时被约束时为 OR 语义（任一匹配即可）。

weekday 约定：Python Monday=0..Sunday=6 → cron Sunday=0..Saturday=6
转换：cron_dow = (python_weekday + 1) % 7
"""

from __future__ import annotations

from datetime import datetime


def _parse_range(part: str) -> tuple[int, int]:
    """解析 'n' 或 'n-m' 为 (start, end)。"""
    if "-" in part:
        start, end = part.split("-", 1)
        return int(start), int(end)
    v = int(part)
    return v, v


def _cron_field_matches(field: str, value: int) -> bool:
    """单个字段匹配：支持 *, n, n-m, a,b,c, */n, a-b/n。"""
    for part in field.split(","):
        if part == "*":
            return True
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                # */n：从 0 开始每 n 个
                if value % step == 0:
                    return True
            else:
                start, end = _parse_range(base)
                if start <= value <= end and (value - start) % step == 0:
                    return True
        elif "-" in part:
            start, end = _parse_range(part)
            if start <= value <= end:
                return True
        else:
            if int(part) == value:
                return True
    return False


def validate_cron(cron_expr: str) -> str | None:
    """校验五段式 cron 表达式。返回 None 表示合法，否则返回错误描述。"""
    if not isinstance(cron_expr, str):
        return "cron expression must be a string"
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return f"expected 5 fields, got {len(fields)}: {cron_expr!r}"
    names = ["minute", "hour", "dom", "month", "dow"]
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    for name, field, (lo, hi) in zip(names, fields, ranges):
        err = _validate_field(field, lo, hi)
        if err:
            return f"{name}: {err}"
    return None


def _validate_field(field: str, lo: int, hi: int) -> str | None:
    """校验单个字段语法与值域。"""
    if not field:
        return "empty field"
    for part in field.split(","):
        if part == "*":
            continue
        try:
            if "/" in part:
                base, step_s = part.split("/", 1)
                step = int(step_s)
                if step <= 0:
                    return f"step must be positive: {part!r}"
                if base == "*":
                    continue
                start, end = _parse_range(base)
            elif "-" in part:
                start, end = _parse_range(part)
            else:
                v = int(part)
                if not (lo <= v <= hi):
                    return f"value {v} out of range [{lo},{hi}]"
                continue
        except ValueError:
            return f"invalid part: {part!r}"
        if start > end:
            return f"range start > end: {part!r}"
        if not (lo <= start <= hi and lo <= end <= hi):
            return f"range {part!r} out of range [{lo},{hi}]"
    return None


def cron_matches(cron_expr: str, dt: datetime) -> bool:
    """判断 dt 是否匹配五段式 cron 表达式。"""
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return False
    minute, hour, dom, month, dow = fields

    # Python Monday=0 → cron Sunday=0
    dow_val = (dt.weekday() + 1) % 7

    m_ok = _cron_field_matches(minute, dt.minute)
    h_ok = _cron_field_matches(hour, dt.hour)
    month_ok = _cron_field_matches(month, dt.month)
    if not (m_ok and h_ok and month_ok):
        return False

    dom_ok = _cron_field_matches(dom, dt.day)
    dow_ok = _cron_field_matches(dow, dow_val)

    dom_unconstrained = dom == "*"
    dow_unconstrained = dow == "*"

    if dom_unconstrained and dow_unconstrained:
        return True
    if dom_unconstrained:
        return dow_ok
    if dow_unconstrained:
        return dom_ok
    # 两者都约束：OR 语义
    return dom_ok or dow_ok
