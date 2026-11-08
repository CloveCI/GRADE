#!/usr/bin/env python3
"""Keep the documentation honest.

Checks, for the maintained markdown (root *.md, docs/ except docs/_legacy, clients/, .github/):
  1. every relative link points at a file or directory that exists;
  2. every `#anchor` on a link to a markdown file matches a heading in that file (GitHub's slug rules);
  3. every page under docs/ carries a "Last verified: YYYY-MM-DD" line near the top
     (exempt: VERIFIED_EXEMPT_PREFIXES and the numbered decision records).
A page last verified more than STALE_DAYS ago is reported as a warning, not a failure.

Run locally: python scripts/ci/check_docs.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STALE_DAYS = 180

CHECKED_PREFIXES = ("docs/", "clients/", ".github/")
SKIP_PREFIXES = ("docs/_legacy/",)
VERIFIED_EXEMPT_PREFIXES = ("docs/_legacy/", "docs/reference/")  # TEMPLATE: add generated or third-party doc folders
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
VERIFIED = re.compile(r"Last verified:\*{0,2}\s*(\d{4}-\d{2}-\d{2})")
FENCE = re.compile(r"^\s*(```|~~~)")


def tracked_markdown() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    files = [p for p in out.splitlines() if p]
    keep = []
    for p in files:
        if p.startswith(SKIP_PREFIXES):
            continue
        if "/" not in p or p.startswith(CHECKED_PREFIXES):  # root files, docs/, clients/, .github/
            keep.append(p)
    return sorted(set(keep))


def slug(heading: str) -> str:
    """GitHub heading anchor: lowercase, drop punctuation except hyphen/underscore/space, spaces to hyphens."""
    s = re.sub(r"`", "", heading.strip().lower())
    s = re.sub(r"[^\w\- ]", "", s, flags=re.UNICODE)
    return s.replace(" ", "-")


def headings(path: Path) -> set[str]:
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    in_fence = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        m = None if in_fence else re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            base = slug(m.group(1))
            n = seen.get(base, 0)
            seen[base] = n + 1
            anchors.add(base if n == 0 else f"{base}-{n}")
    return anchors


def iter_links(text: str):
    in_fence = False
    for no, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = re.sub(r"`[^`]*`", "", line)  # ignore inline code
        for m in LINK.finditer(line):
            yield no, m.group(1)


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}

    for rel in tracked_markdown():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8", errors="replace")

        for no, target in iter_links(text):
            if re.match(r"^(https?:|mailto:|tel:)", target):
                continue
            file_part, _, frag = target.partition("#")
            dest = path if not file_part else (path.parent / file_part).resolve()
            if file_part and not dest.exists():
                errors.append(f"{rel}:{no}: broken link -> {target}")
                continue
            if frag and dest.is_file() and dest.suffix == ".md":
                if dest not in anchor_cache:
                    anchor_cache[dest] = headings(dest)
                if frag.lower() not in anchor_cache[dest]:
                    errors.append(f"{rel}:{no}: no heading '#{frag}' in {dest.relative_to(ROOT).as_posix()}")

        if rel.startswith("docs/") and not rel.startswith(VERIFIED_EXEMPT_PREFIXES) and not re.match(r"docs/architecture/decisions/\d{4}-", rel):
            head = "\n".join(text.splitlines()[:14])
            m = VERIFIED.search(head)
            if not m:
                errors.append(f"{rel}: missing 'Last verified: YYYY-MM-DD' line in the first lines")
            else:
                age = (date.today() - datetime.strptime(m.group(1), "%Y-%m-%d").date()).days
                if age > STALE_DAYS:
                    warnings.append(f"{rel}: last verified {age} days ago")

    for w in warnings:
        print("warning:", w)
    if errors:
        print("documentation problems:")
        for e in errors:
            print("  -", e)
        return 1
    print(f"ok: links, anchors and 'Last verified' lines are valid in {len(tracked_markdown())} maintained markdown files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
