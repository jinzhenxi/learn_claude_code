---
name: git-commit
description: Conventional Commits rules for commit messages; includes examples and a validation script.
---

# Git Commit

Write commit messages in the Conventional Commits format:

```
<type>(<scope>): <subject>

<body>
```

## Rules

- `type` is one of: feat, fix, docs, style, refactor, test, chore.
- Subject is imperative, lowercase, no trailing period, max 50 characters.
- Body wraps at 72 characters and explains *why*, not *what* (the diff shows what).
- Breaking changes append `!` after the type/scope and add a `BREAKING CHANGE:` footer.

## Bundled resources

- `references/examples.md` — good and bad commit messages side by side.
- `scripts/validate_commit.sh <message-file>` — checks a message against these rules.
