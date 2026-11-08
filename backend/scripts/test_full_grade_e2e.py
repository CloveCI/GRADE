#!/usr/bin/env python3
"""End-to-end grade workflow test for cie-dm (API + DB + evaluate)."""

from __future__ import annotations

import json
import os
import sys
import time
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


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def main() -> int:
    import requests

    _load_dotenv()
    base = os.environ.get("GRADE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    exam_id = "cie-dm"
    sheet_id = os.environ.get("GRADE_TEST_SHEET_ID", "3f0437fc-196b-42f6-a124-39a234e683cd")

    print(f"=== Full grade E2E test ({exam_id}) ===\n")

    # 1. Health
    for attempt in range(12):
        try:
            r = requests.get(f"{base}/health", timeout=5)
            if r.status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    else:
        _fail(f"API not reachable at {base}/health")
    health = r.json()
    db = health.get("database") or {}
    if not db.get("connected"):
        _fail(f"Database not connected: {db.get('error')}")
    _ok(f"API healthy, DB connected")

    # 2. Sheet + question mappings
    r = requests.get(f"{base}/api/sheet/{sheet_id}/question-regions", timeout=30)
    if r.status_code != 200:
        _fail(f"question-regions: {r.status_code} {r.text[:200]}")
    qr = r.json().get("question_regions") or []
    if len(qr) != 6:
        _fail(f"Expected 6 question_regions, got {len(qr)}")
    _ok(f"question_regions: {len(qr)} questions")
    for item in qr:
        qi = int(item.get("question_index", -1))
        ps, pe = item.get("page_start"), item.get("page_end")
        print(f"    Q{qi+1}: pages {ps}-{pe}")

    r = requests.get(f"{base}/api/sheet/{sheet_id}/question-answers", timeout=30)
    if r.status_code != 200:
        _fail(f"question-answers: {r.status_code} {r.text[:200]}")
    qa = r.json().get("question_answers") or []
    _ok(f"question_answers: {len(qa)} rows")

    # 3. Preview
    r = requests.get(f"{base}/api/sheet/{sheet_id}/preview?rebuild=false", timeout=120)
    if r.status_code != 200:
        _fail(f"preview meta: {r.status_code} {r.text[:200]}")
    preview = r.json()
    pages = int(preview.get("page_count") or preview.get("pages") or 0)
    if pages < 5:
        _fail(f"Expected >=5 preview pages, got {pages}")
    _ok(f"preview: {pages} pages, {len(preview.get('regions') or [])} regions")

    # 4. Evaluate (full grade)
    print("\n  Running POST /evaluate (may take several minutes)...")
    t0 = time.time()
    r = requests.post(
        f"{base}/evaluate",
        json={
            "sheet_id": sheet_id,
            "exam_id": exam_id,
            "expected_num_regions": 6,
            "force_regrade": True,
        },
        timeout=900,
    )
    elapsed = round(time.time() - t0, 1)
    if r.status_code != 200:
        _fail(f"evaluate: {r.status_code} after {elapsed}s — {r.text[:400]}")
    result = r.json()
    questions = result.get("questions") or []
    if len(questions) != 6:
        _fail(f"Expected 6 graded questions, got {len(questions)}")
    flags = result.get("flags") or []
    if "segmentation_v3" not in flags:
        _fail(f"Missing segmentation_v3 flag in result: {flags}")
    _ok(
        f"evaluate: {len(questions)} questions in {elapsed}s, "
        f"total {result.get('total_marks')}/{result.get('max_total')}, flags={flags[:4]}"
    )

    for i, q in enumerate(questions):
        qid = q.get("question_id") or f"Q{i+1}"
        ocr = (q.get("ocr_raw") or q.get("student_answer") or "")[:80].replace("\n", " ")
        marks = q.get("awarded_marks")
        max_m = q.get("max_marks")
        print(f"    {qid}: {marks}/{max_m} — {ocr}…")

    # 5. Persisted question answers after evaluate
    r = requests.get(f"{base}/api/sheet/{sheet_id}/question-answers", timeout=30)
    qa2 = r.json().get("question_answers") or []
    formatted = sum(1 for a in qa2 if str(a.get("formatted_answer_text") or "").strip())
    if formatted < 4:
        _fail(f"Expected formatted answers for most questions, got {formatted}/{len(qa2)}")
    _ok(f"post-evaluate formatted answers: {formatted}/{len(qa2)}")

    # 6. Result retrieval
    rid = result.get("result_id")
    r = requests.get(f"{base}/result/{rid}", timeout=30)
    if r.status_code != 200 or len(r.json().get("questions") or []) != 6:
        _fail(f"result/{rid} retrieval failed")
    _ok(f"result/{rid} retrievable")

    print("\n=== All grade workflow checks passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
