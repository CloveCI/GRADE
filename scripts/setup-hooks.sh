#!/bin/sh
# One-time, per clone: use the versioned hooks in scripts/githooks (hygiene, docs, secrets, lint).
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath scripts/githooks
chmod +x scripts/githooks/pre-commit 2>/dev/null || true
echo "git hooks enabled (core.hooksPath=scripts/githooks)."
echo "optional but recommended: install gitleaks and ruff so the pre-commit hook can use them."
