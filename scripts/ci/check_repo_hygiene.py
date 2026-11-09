#!/usr/bin/env python3
"""Fail on things that must never be tracked: dependency/build output, real env files, caches, big binaries.

.gitignore alone does not stop this (files added before the rule, or force-added), so this checks what git actually tracks.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 1_500_000  # files above this need an entry in .github/large-files-allowlist.txt

FORBIDDEN_DIRS = re.compile(r"(^|/)(node_modules|\.next|dist|__pycache__|\.venv|venv|\.pytest_cache|\.ruff_cache)/")
FORBIDDEN_NAMES = re.compile(r"(^|/)(\.DS_Store|Thumbs\.db|.*\.pyc|.*\.log|.*\.pem|.*\.p12|.*\.pfx)$")
ENV_FILE = re.compile(r"(^|/)\.env(\..+)?$")
ENV_OK = re.compile(r"\.(example|template|sample)$")
# Paths exempt from these checks, e.g. test fixtures that intentionally look like secrets. TEMPLATE: adjust per repo.
ALLOWED_PREFIXES: tuple[str, ...] = ()


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def main() -> int:
    allow = set()
    allow_file = ROOT / ".github" / "large-files-allowlist.txt"
    if allow_file.exists():
        allow = {ln.strip() for ln in allow_file.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")}

    problems: list[str] = []
    for path in tracked():
        if path.startswith(ALLOWED_PREFIXES):
            continue
        if FORBIDDEN_DIRS.search(path) or FORBIDDEN_NAMES.search(path):
            problems.append(f"generated/forbidden file is tracked: {path}")
        if ENV_FILE.search(path) and not ENV_OK.search(path):
            problems.append(f"env file is tracked (only *.example is allowed): {path}")
        f = ROOT / path
        if f.is_file() and path not in allow and f.stat().st_size > MAX_BYTES:
            problems.append(f"{path} is {f.stat().st_size / 1_000_000:.1f} MB (limit {MAX_BYTES / 1_000_000:.1f} MB; "
                            f"store large assets outside git, or add the path to .github/large-files-allowlist.txt)")

    if problems:
        print("repo hygiene problems:")
        for p in problems[:50]:
            print("  -", p)
        if len(problems) > 50:
            print(f"  ... and {len(problems) - 50} more")
        return 1
    print("ok: no generated output, real env files or oversized files are tracked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
