#!/usr/bin/env python3
"""Backfill sheet question_regions, sheet_question_answers, and RAG chunks for an exam."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    env_path = _repo_root() / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill question answers + RAG for exam sheets")
    parser.add_argument("--exam-id", default="cie-dm", help="Exam id to backfill (default: cie-dm)")
    parser.add_argument("--sheet-id", default=None, help="Optional single sheet id")
    parser.add_argument("--skip-keys", action="store_true", help="Skip answer-key RAG re-index")
    args = parser.parse_args()

    _load_dotenv()
    sys.path.insert(0, str(_repo_root() / "src"))

    from autograder.db import get_rag_chunks_for_sheet, init_db, list_sheet_question_answers, list_sheets
    from autograder.rag.ingest import ingest_keys_rag, ingest_sheet_rag

    init_db()

    exam_id = args.exam_id.strip()
    if args.sheet_id:
        sheets = [s for s in list_sheets(exam_id=exam_id, limit=1000) if s["id"] == args.sheet_id]
        if not sheets:
            print(f"No sheet {args.sheet_id} for exam {exam_id}")
            return 1
    else:
        sheets = list_sheets(exam_id=exam_id, limit=1000)

    if not sheets:
        print(f"No sheets found for exam_id={exam_id}")
        return 1

    if not args.skip_keys:
        keys_out = ingest_keys_rag(exam_id, force=True)
        print("keys:", json.dumps(keys_out, indent=2))

    failures = 0
    for sheet in sheets:
        sid = str(sheet["id"])
        print(f"\n=== Backfill sheet {sid} ({sheet.get('filename')}) ===")
        out = ingest_sheet_rag(sid, force=True)
        print("ingest:", json.dumps(out, indent=2))
        if out.get("status") not in {"success", "cached"}:
            failures += 1
            continue

        answers = list_sheet_question_answers(sid)
        print(f"question_answers: {len(answers)} rows")
        for a in answers:
            print(
                f"  {a.get('question_id')}: pages {a.get('page_start')}-{a.get('page_end')} "
                f"raw_len={len(str(a.get('raw_ocr_text') or ''))}"
            )

        chunks = get_rag_chunks_for_sheet(sid, limit=500)
        tagged = sum(1 for c in chunks if (c.get("meta") or {}).get("question_id"))
        print(f"rag_chunks: {len(chunks)} total, {tagged} with question_id")

    print(f"\nDone. sheets={len(sheets)} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
