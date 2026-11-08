#!/usr/bin/env python3
"""
Verify GRADE bundle → ingest → evaluate workflow against Postgres.

Usage (from backend/):
  $env:PYTHONPATH = "src"
  python scripts/verify_workflow.py
  python scripts/verify_workflow.py --exam-id daa --sheet-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    env_path = REPO / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def verify_db_linkage(exam_id: Optional[str], sheet_id: Optional[str]) -> int:
    from autograder.db import (
        database_status,
        get_rag_chunks_for_sheet,
        get_sheet,
        list_answer_keys,
        list_exams_with_counts,
        list_sheets,
    )
    from autograder.embeddings import embed_text_local, retrieve_top_k
    from autograder.rag.ingest import keys_document_id, sheet_document_id
    from autograder.rag.retrieval import hybrid_search_for_exam, match_answer_key

    print("\n=== Database ===")
    st = database_status()
    if not st.get("connected"):
        _fail(st.get("error") or "Database not connected")
        return 1
    _ok(f"Postgres connected; rag_ready={st.get('rag_ready')} evaluation_ready={st.get('evaluation_ready')}")

    exams = list_exams_with_counts(limit=20)
    if not exams:
        _warn("No exams in database — upload a bundle first.")
        return 2

    print("\n=== Exams (linked keys + sheets) ===")
    for e in exams[:10]:
        print(
            f"  {e.get('exam_id')}: keys={e.get('key_count', 0)} "
            f"sheets={e.get('sheet_count', 0)} results={e.get('result_count', 0)}"
        )

    target_exam = exam_id or (exams[0].get("exam_id") if exams else None)
    if not target_exam:
        _fail("No exam_id to verify")
        return 1

    keys = list_answer_keys(str(target_exam))
    sheets = [s for s in list_sheets(limit=50) if str(s.get("exam_id") or "") == str(target_exam)]

    print(f"\n=== Exam '{target_exam}' ===")
    print(f"  Answer keys: {len(keys)}")
    for k in keys[:8]:
        emb = k.get("embedding") or []
        print(
            f"    {k.get('question_id')} sort={k.get('sort_order')} "
            f"max={k.get('max_marks')} emb_dims={len(emb)}"
        )
    if len(keys) > 8:
        print(f"    ... +{len(keys) - 8} more")

    if not sheets:
        _warn(f"No sheets linked to exam_id={target_exam}")
        return 2

    target_sheet = sheet_id
    if not target_sheet:
        target_sheet = str(sheets[0].get("id") or sheets[0].get("sheet_id") or "")
    row = get_sheet(target_sheet)
    if not row:
        _fail(f"sheet_id not found: {target_sheet}")
        return 1

    sheet_exam = str(row.get("exam_id") or "")
    if sheet_exam != str(target_exam):
        _fail(f"Sheet exam_id={sheet_exam!r} != target exam {target_exam!r}")
        return 1
    _ok(f"Sheet {target_sheet[:12]}… linked to exam {sheet_exam}")

    print("\n=== RAG corpora (embeddings in rag_chunks) ===")
    key_doc = keys_document_id(str(target_exam))
    sheet_doc = sheet_document_id(target_sheet)
    _ok(f"Key corpus document_id={key_doc}")
    _ok(f"Sheet corpus document_id={sheet_doc}")

    chunks = get_rag_chunks_for_sheet(target_sheet, limit=500)
    print(f"  Sheet chunks: {len(chunks)}")
    regions: List[str] = []
    for c in chunks[:12]:
        meta = c.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        rid = meta.get("region_id") or "?"
        regions.append(str(rid))
        preview = (c.get("text") or c.get("text_content") or "")[:60].replace("\n", " ")
        print(f"    {rid}: {preview}…")
    if len(chunks) > 12:
        print(f"    ... +{len(chunks) - 12} chunks")

    if not chunks:
        _warn("No RAG chunks for sheet — run ingest or re-upload bundle.")
    elif regions:
        _ok(f"Answer regions indexed: {', '.join(sorted(set(regions))[:10])}")

    print("\n=== Region -> key matching (embedding alignment) ===")
  # Simulate evaluate's per-region key pick using placeholder student text per region
    for i, c in enumerate(chunks[: min(6, len(chunks))]):
        meta = c.get("meta") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        student_stub = (c.get("text") or c.get("text_content") or f"region {i}")[:200]
        chosen = match_answer_key(i, student_stub, keys, top_k=3)
        top = retrieve_top_k(student_stub, keys, top_k=2)
        sims = [round(s, 3) for _, s in top] if top else []
        print(
            f"  patch {i} ({meta.get('region_id', '?')}) -> key {chosen.get('question_id')} "
            f"(top sims: {sims})"
        )

    print("\n=== Hybrid RAG retrieval (keys + sheet) ===")
    if keys:
        q = f"{keys[0].get('question_id')} {(keys[0].get('expected_answer') or '')[:80]}"
        hits = hybrid_search_for_exam(target_sheet, str(target_exam), q, top_k=5)
        print(f"  Query: {q[:60]}…")
        for h in hits[:5]:
            meta = h.get("meta") or {}
            kind = meta.get("kind") or ("answer_key" if str(h.get("document_id", "")).startswith("keys_") else "sheet")
            print(f"    [{kind}] score={h.get('fused_score', h.get('distance'))} {str(h.get('text_content', ''))[:50]}…")
        if hits:
            _ok("Dual-corpus hybrid search returned hits")
        else:
            _warn("Hybrid search returned no hits")

    print("\n=== Recent evaluation results ===")
    from autograder.db import get_result, list_results

    results = [r for r in list_results(exam_id=str(target_exam), limit=5)]
    if not results:
        _warn("No saved evaluations for this exam — click Evaluate in the UI.")
    else:
        for r in results[:3]:
            rid = r.get("id") or r.get("result_id")
            full = get_result(str(rid)) if rid else None
            qs = (full or {}).get("questions") or []
            n = len(qs) if isinstance(qs, list) else 0
            print(f"  result {str(rid)[:12]}… total={r.get('total_marks')}/{r.get('max_total')} questions={n}")
            for i, qn in enumerate(qs[:6]):
                if isinstance(qn, dict):
                    print(
                        f"      [{i}] {qn.get('question_id')} region={qn.get('region_index')} "
                        f"{qn.get('awarded_marks')}/{qn.get('max_marks')} "
                        f"ans_len={len(str(qn.get('student_answer') or ''))}"
                    )

    return 0


def verify_http(base: str, exam_id: str, sheet_id: str) -> int:
    try:
        import urllib.request
    except ImportError:
        return 0

    print(f"\n=== HTTP API ({base}) ===")
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=5) as resp:
            if resp.status != 200:
                _warn(f"health status {resp.status}")
                return 0
        _ok("API health OK")
    except Exception as e:
        _warn(f"API not reachable: {e}")
        return 0

    try:
        import urllib.error

        body = json.dumps(
            {
                "sheet_id": sheet_id,
                "exam_id": exam_id,
                "top_k": 3,
                "expected_num_regions": 6,
                "use_consensus_ocr": False,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/evaluate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        n = len(data.get("questions") or [])
        _ok(f"POST /evaluate → {n} questions, total={data.get('total_marks')}/{data.get('max_total')}")
        for i, q in enumerate((data.get("questions") or [])[:6]):
            print(
                f"    Q{i}: {q.get('question_id')} region={q.get('region_index')} "
                f"score={q.get('awarded_marks')}/{q.get('max_marks')} "
                f"student_len={len(q.get('student_answer') or '')}"
            )
        return 0
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        _fail(f"POST /evaluate HTTP {e.code}: {detail}")
        return 1
    except Exception as e:
        _fail(f"POST /evaluate failed: {e}")
        return 1


def main() -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(description="Verify GRADE ingest + evaluate workflow")
    p.add_argument("--exam-id", help="Exam to inspect (default: latest)")
    p.add_argument("--sheet-id", help="Sheet UUID (default: first sheet for exam)")
    p.add_argument("--api", default="http://127.0.0.1:8000", help="API base URL for live evaluate")
    p.add_argument("--run-evaluate", action="store_true", help="POST /evaluate (slow; needs API + OCR)")
    args = p.parse_args()

    print("GRADE workflow verification")
    code = verify_db_linkage(args.exam_id, args.sheet_id)
    if code != 0 and code != 2:
        return code

    if args.run_evaluate and args.exam_id and args.sheet_id:
        return verify_http(args.api, args.exam_id, args.sheet_id) or code
    if args.run_evaluate:
        _warn("Pass --exam-id and --sheet-id with --run-evaluate")
    return code


if __name__ == "__main__":
    sys.exit(main())
