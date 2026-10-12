---
name: sql-style
description: Rules for writing readable, index-friendly SQL (formatting, naming, and anti-patterns).
---

# SQL Style

Follow these rules whenever you write or review SQL.

## Formatting

- Use lowercase SQL keywords are banned: write `select`, `from`, `where` in lowercase consistently, or uppercase consistently within one query.
- One selected column per line when the query has more than three columns.
- Align `join` conditions under their tables; indent continuations by 4 spaces.

## Naming

- Table and column names use `snake_case` and are singular: `user_order`, not `UserOrders`.
- Boolean columns start with `is_` / `has_`: `is_deleted`.
- Foreign keys are `<referenced_table>_id`: `user_id`.

## Anti-patterns

- Never `select *` in production queries; list columns explicitly.
- Do not wrap indexed columns in functions in `where` (`where date(created_at) = ...`) — it defeats the index.
- Avoid implicit joins (comma-separated tables); always write explicit `join`.
- Prefer `union all` over `union` unless deduplication is required.

## Quick example

```sql
select
    id,
    user_id,
    amount
from user_order
where status = 'paid'
  and created_at >= '2026-01-01'
order by created_at desc;
```
