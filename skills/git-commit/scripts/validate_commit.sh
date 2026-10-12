#!/usr/bin/env bash
# Validate a commit message against minimal Conventional Commits rules.
# Usage: validate_commit.sh <message-file>
set -euo pipefail

file="${1:?usage: validate_commit.sh <message-file>}"
first=$(head -n 1 "$file")

types_re='^(feat|fix|docs|style|refactor|test|chore)(\([a-z0-9_-]+\))?!?: .+'
if ! grep -Eq "$types_re" <<<"$first"; then
    echo "invalid header: $first" >&2
    exit 1
fi
if [ "${#first}" -gt 72 ]; then
    echo "header too long (${#first} > 72)" >&2
    exit 1
fi
echo "valid: $first"
