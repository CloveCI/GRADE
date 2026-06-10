#!/usr/bin/env python3
"""
End-to-end test for GRADE RAG ingestion and per-answer retrieval.

Exercises the same path as POST /evaluate (without LLM grading):
  1. Ingest answer keys + sheet into ``public.rag_chunks`` (``ingest_keys_rag``, ``ingest_sheet_rag``)
  2. For each OCR region on the sheet: match answer key → format student text → hybrid RAG retrieval
  3. Report key-corpus vs sheet-corpus chunk hits (vector + fused scores)
  4. Verify database links (``sheets``, ``answer_keys``, ``answer_key_chunks``, ``rag_chunks``)

Requires ``GRADE_DATABASE_URL`` (or ``DATABASE_URL``) and ``pip install -e ".[postgres]"``.

Usage (from repo root):
  set PYTHONPATH=src
  python scripts/test_rag_ingestion_retrieval.py
  python scripts/test_rag_ingestion_retrieval.py --exam-id midterm --sheet-id <uuid>
  python scripts/test_rag_ingestion_retrieval.py --ingest --format-llm
  python scripts/test_rag_ingestion_retrieval.py --ingest --heuristic-only --top-k 5
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _parse_meta(meta: Any) -> Dict[str, Any]:
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str) and meta:
        try:
            return json.loads(meta)
        except json.JSONDecodeError:
            return {}
    return {}


def _short(text: str, n: int = 72) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _database_url() -> str:
    return (os.environ.get("GRADE_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()


def count_rag_chunks_for_document(document_id: str) -> int:
    from autograder.db import _pg_connect, _pg_execute
    from psycopg.rows import dict_row

    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(
                cur,
                "SELECT COUNT(*)::int AS c FROM public.rag_chunks WHERE document_id = %s",
                (document_id,),
            )
            row = cur.fetchone()
    return int((row or {}).get("c") or 0)


def fetch_rag_chunk_row(chunk_id: str) -> Optional[Dict[str, Any]]:
    from autograder.db import _pg_connect, _pg_execute
    from psycopg.rows import dict_row

    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(
                cur,
                """
                SELECT chunk_id, document_id, chunk_index, text_content, meta
                FROM public.rag_chunks
                WHERE chunk_id = %s
                """,
                (chunk_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    d["meta"] = _parse_meta(d.get("meta"))
    return d


def fetch_answer_key_row(key_id: str) -> Optional[Dict[str, Any]]:
    from autograder.db import _pg_connect, _pg_execute
    from psycopg.rows import dict_row

    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(
                cur,
                """
                SELECT id, exam_id, question_id, expected_answer
                FROM public.answer_keys
                WHERE id = %s
                """,
                (key_id,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def fetch_answer_key_chunk_row(chunk_id: str) -> Optional[Dict[str, Any]]:
    from autograder.db import _pg_connect, _pg_execute
    from psycopg.rows import dict_row

    with _pg_connect(row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            _pg_execute(
                cur,
                """
                SELECT chunk_id, answer_key_id, chunk_index, text_content
                FROM public.answer_key_chunks
                WHERE chunk_id = %s
                """,
                (chunk_id,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


def verify_chunk_database_links(
    chunk_id: str,
    *,
    exam_id: str,
    sheet_id: str,
    keys_by_id: Dict[str, Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """
    Confirm a retrieved ``rag_chunks`` row is wired to sheets / answer_keys / answer_key_chunks.
    """
    errors: List[str] = []
    row = fetch_rag_chunk_row(chunk_id)
    if not row:
        # retrieve_context_for_grading may reference key_{uuid} without a rag_chunks row
        rest = chunk_id[4:] if chunk_id.startswith("key_") else ""
        is_key_subchunk = bool(re.search(r"_c\d+$", rest))
        if chunk_id.startswith("key_") and not is_key_subchunk:
            key_id = rest
            ak = fetch_answer_key_row(key_id)
            if ak and str(ak.get("exam_id") or "") == exam_id:
                return True, []
        return False, [f"chunk_id {chunk_id!r} not in rag_chunks"]

    meta = row.get("meta") or {}
    doc = str(row.get("document_id") or "")
    kind = str(meta.get("kind") or "")

    if doc.startswith("keys_"):
        if kind and kind != "answer_key":
            errors.append(f"{chunk_id}: meta.kind={kind!r} expected answer_key")
        if doc != f"keys_{exam_id}":
            errors.append(f"{chunk_id}: document_id={doc!r} != keys_{exam_id!r}")
        meta_exam = str(meta.get("exam_id") or "")
        if meta_exam and meta_exam != exam_id:
            errors.append(f"{chunk_id}: meta.exam_id={meta_exam!r} != {exam_id!r}")

        key_id = str(meta.get("key_id") or "")
        if chunk_id.startswith("key_") and not key_id:
            key_id = chunk_id.removeprefix("key_").split("_c")[0]
        if key_id:
            if key_id not in keys_by_id:
                ak = fetch_answer_key_row(key_id)
                if not ak:
                    errors.append(f"{chunk_id}: key_id {key_id!r} missing from answer_keys")
                elif str(ak.get("exam_id") or "") != exam_id:
                    errors.append(f"{chunk_id}: answer_keys.exam_id mismatch for {key_id!r}")
            akc_id = chunk_id.removeprefix("key_") if "_c" in chunk_id else None
            if akc_id:
                akc = fetch_answer_key_chunk_row(akc_id)
                if not akc:
                    errors.append(
                        f"{chunk_id}: not found in answer_key_chunks (looked up {akc_id!r})"
                    )
                elif str(akc.get("answer_key_id") or "") != key_id:
                    errors.append(
                        f"{chunk_id}: answer_key_chunks.answer_key_id="
                        f"{akc.get('answer_key_id')!r} != {key_id!r}"
                    )
        else:
            errors.append(f"{chunk_id}: no key_id in meta for answer-key chunk")

    elif doc.startswith("sheet_"):
        if kind and kind != "sheet":
            errors.append(f"{chunk_id}: meta.kind={kind!r} expected sheet")
        expected_doc = f"sheet_{sheet_id}"
        if doc != expected_doc:
            errors.append(f"{chunk_id}: document_id={doc!r} != {expected_doc!r}")
        meta_sheet = str(meta.get("sheet_id") or "")
        if meta_sheet and meta_sheet != sheet_id:
            errors.append(f"{chunk_id}: meta.sheet_id={meta_sheet!r} != {sheet_id!r}")
        meta_exam = str(meta.get("exam_id") or "")
        if meta_exam and meta_exam != exam_id:
            errors.append(f"{chunk_id}: meta.exam_id={meta_exam!r} != {exam_id!r}")
    else:
        errors.append(f"{chunk_id}: unexpected document_id={doc!r}")

    return (len(errors) == 0), errors


def regions_from_sheet_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Assemble full OCR text per region_id from all in-scope RAG chunks."""
    from autograder.rag.boundaries import assemble_region_text_from_chunks

    by_region: Dict[str, List[Dict[str, Any]]] = {}
    for c in chunks:
        meta = _parse_meta(c.get("meta"))
        rid = str(meta.get("region_id") or meta.get("region") or "")
        if not rid:
            rid = f"chunk_{c.get('chunk_index', 0)}"
        by_region.setdefault(rid, []).append(c)

    out: List[Dict[str, Any]] = []
    for rid in sorted(by_region.keys()):
        region_chunks = by_region[rid]
        full_text = assemble_region_text_from_chunks(region_chunks, rid)
        if not full_text.strip():
            best = max(
                region_chunks,
                key=lambda x: len(str(x.get("text_content") or "")),
            )
            full_text = str(best.get("text_content") or "").strip()
        out.append(
            {
                "region_id": rid,
                "text": full_text,
                "chunk_id": region_chunks[0].get("chunk_id") if region_chunks else None,
                "chunk_index": region_chunks[0].get("chunk_index") if region_chunks else 0,
            }
        )
    return out


def _hit_score(hit: Dict[str, Any]) -> float:
    if hit.get("score") is not None:
        return float(hit["score"])
    if hit.get("similarity") is not None:
        return float(hit["similarity"])
    if hit.get("vector_distance") is not None:
        return max(0.0, 1.0 - float(hit["vector_distance"]))
    dist = float(hit.get("distance") or 1.0)
    return max(0.0, 1.0 - dist)


def _normalize_display_text(text: str) -> str:
    """Collapse PDF/OCR newlines so wrapped output is readable paragraphs."""
    import re

    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", t)
    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    if len(lines) >= 6:
        short = sum(1 for ln in lines if len(ln.split()) <= 5)
        # Key.pdf text layer is often one token per line
        if short / len(lines) >= 0.65:
            return re.sub(r"\s+", " ", " ".join(lines)).strip()
    paras: List[str] = []
    for block in re.split(r"\n\s*\n+", t):
        line = re.sub(r"\s+", " ", block.replace("\n", " ")).strip()
        if line:
            paras.append(line)
    if not paras and lines:
        return re.sub(r"\s+", " ", " ".join(lines)).strip()
    return "\n\n".join(paras) if paras else ""


def _wrap_block(text: str, width: int = 88) -> List[str]:
    import textwrap

    normalized = _normalize_display_text(text)
    if not normalized:
        return ["(empty)"]
    lines: List[str] = []
    for para in normalized.split("\n\n"):
        lines.extend(textwrap.wrap(para, width=width) or [""])
        if para != normalized.split("\n\n")[-1]:
            lines.append("")
    return lines or ["(empty)"]


_comparison_out_path: Optional[Path] = None


def print_bounded_evaluation(ev: Any) -> None:
    """Print full bounded key/sheet answers, all chunks, boundaries, and on-the-spot score."""
    from autograder.rag.boundaries import BoundedEvaluation

    if not isinstance(ev, BoundedEvaluation):
        return
    sep = "=" * 92
    print(f"\n{sep}")
    from autograder.rag.boundaries import is_multipart_question

    fmt = ev.format_method or "?"
    bounds = ""
    if ev.sheet_answer_start is not None and ev.sheet_answer_end is not None:
        bounds = f" | sheet @{ev.sheet_answer_start}-{ev.sheet_answer_end}"
    mp = "multipart (a)+(b)" if is_multipart_question(
        f"{ev.key.question_prompt}\n\n{ev.key.assembled_text}"
    ) else "single-part"
    print(
        f"  BOUNDED COMPARISON — {ev.question_id} | region {ev.region_id} "
        f"| {mp} | awarded {ev.awarded_marks}/{ev.max_marks} "
        f"| sim={ev.similarity_raw:.4f} score={ev.similarity_score:.4f} "
        f"| format={fmt}{bounds}"
    )
    print(sep)

    k = ev.key
    print(f"\n  KEY {k.start_marker} … {k.end_marker}")
    if k.question_prompt:
        print(f"  Question: {k.question_prompt}")
    print(f"  Chunks ({len(k.chunk_spans)}) — scoped to {ev.question_id} only:")
    for i, sp in enumerate(k.chunk_spans):
        sim_s = (
            f" vs-student={sp.similarity_to_student:.4f}"
            if sp.similarity_to_student is not None
            else ""
        )
        print(
            f"    [{i + 1}] {sp.chunk_id} idx={sp.chunk_index} "
            f"chars={sp.char_start}-{sp.char_end}{sim_s}"
        )
    print("  Assembled model answer (complete):")
    for line in _wrap_block(k.assembled_text):
        print(f"    {line}")

    s = ev.sheet_raw
    print(f"\n  SHEET {s.start_marker} … {s.end_marker}")
    print(f"  Chunks ({len(s.chunk_spans)}) — scoped to {ev.region_id} only:")
    for i, sp in enumerate(s.chunk_spans):
        sim_s = (
            f" vs-student={sp.similarity_to_student:.4f}"
            if sp.similarity_to_student is not None
            else ""
        )
        print(
            f"    [{i + 1}] {sp.chunk_id} idx={sp.chunk_index} "
            f"chars={sp.char_start}-{sp.char_end}{sim_s}"
        )
    print("  Assembled OCR (complete, from region chunks):")
    for line in _wrap_block(s.assembled_text):
        print(f"    {line}")
    print("  Formatted student answer:")
    for line in _wrap_block(ev.sheet_formatted):
        print(f"    {line}")

    if ev.chunk_alignments:
        print("\n  Chunk alignment (key chunk → best sheet chunk):")
        for a in ev.chunk_alignments:
            print(
                f"    {a['key_chunk_id']} [{a['key_chars']}] → "
                f"{a['sheet_chunk_id']} [{a['sheet_chars']}] "
                f"sim={a['chunk_similarity']}"
            )
    print(sep)

    if _comparison_out_path is not None:
        lines = [
            f"\n{sep}\nBOUNDED — {ev.question_id} | {ev.region_id}\n",
            f"SCORE: {ev.awarded_marks}/{ev.max_marks} sim={ev.similarity_raw:.4f} format={fmt}\n",
            f"KEY {k.start_marker} question: {k.question_prompt}\n",
            _normalize_display_text(k.assembled_text) + "\n",
            f"SHEET {s.start_marker}\n",
            _normalize_display_text(s.assembled_text) + "\n",
            f"FORMATTED STUDENT ({fmt})\n",
            _normalize_display_text(ev.sheet_formatted) + "\n",
        ]
        with _comparison_out_path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines))


def print_side_by_side_comparison(
    *,
    question_id: str,
    region_id: str,
    region_index: int,
    key: Dict[str, Any],
    raw_ocr: str,
    formatted_student: str,
    format_method: str,
    key_hits: List[Dict[str, Any]],
    sheet_hits: List[Dict[str, Any]],
    top_n: int = 3,
    max_excerpt_chars: int = 1200,
) -> None:
    """Print KEY vs STUDENT text comparison (model answer, LLM-formatted OCR, RAG excerpts)."""
    sep = "=" * 92
    print(f"\n{sep}")
    print(f"  COMPARISON — {question_id}  |  region {region_id} (index {region_index})")
    print(sep)

    model = str(key.get("expected_answer") or "").strip()
    print("\n  ┌─ KEY SIDE (official model answer from Key.pdf) ─────────────────────────────")
    for line in _wrap_block(model):
        print(f"  │ {line}")
    print("  ├─ Retrieved key chunks (hybrid RAG) ─────────────────────────────────────────")
    if not key_hits:
        print("  │ (no key chunks retrieved)")
    for i, h in enumerate(key_hits[:top_n]):
        meta = h.get("meta") or {}
        score = _hit_score(h)
        cid = h.get("chunk_id") or "?"
        body = (h.get("text_content") or "").strip()
        if len(body) > max_excerpt_chars:
            body = body[: max_excerpt_chars - 1] + "…"
        raw = h.get("similarity")
        raw_s = f" sim={float(raw):.4f}" if raw is not None else ""
        print(f"  │ [{i + 1}] score={score:.4f}{raw_s} chunk={cid} q={meta.get('question_id') or '-'}")
        for line in _wrap_block(body):
            print(f"  │     {line}")
    print("  └────────────────────────────────────────────────────────────────────────────")

    print("\n  ┌─ STUDENT SIDE (answer sheet — DocScanner OCR) ─────────────────────────────")
    print("  │ Raw OCR:")
    for line in _wrap_block(raw_ocr, width=84):
        print(f"  │   {line}")
    print(f"  ├─ After formatting ({format_method}):")
    for line in _wrap_block(formatted_student, width=84):
        print(f"  │   {line}")
    print("  ├─ Retrieved sheet chunks (hybrid RAG, region-aware) ───────────────────────")
    if not sheet_hits:
        print("  │ (no sheet chunks retrieved)")
    for i, h in enumerate(sheet_hits[:top_n]):
        meta = h.get("meta") or {}
        score = _hit_score(h)
        cid = h.get("chunk_id") or "?"
        rid = meta.get("region_id") or "-"
        body = (h.get("text_content") or "").strip()
        if len(body) > max_excerpt_chars:
            body = body[: max_excerpt_chars - 1] + "…"
        raw = h.get("similarity")
        raw_s = f" sim={float(raw):.4f}" if raw is not None else ""
        print(f"  │ [{i + 1}] score={score:.4f}{raw_s} region={rid} chunk={cid}")
        for line in _wrap_block(body):
            print(f"  │     {line}")
    print("  └────────────────────────────────────────────────────────────────────────────")
    print(sep)

    if _comparison_out_path is not None:
        import io

        buf = io.StringIO()
        buf.write(f"\n{sep}\n  COMPARISON — {question_id}  |  region {region_id}\n{sep}\n\n")
        buf.write("KEY SIDE — official model answer\n")
        buf.write(_normalize_display_text(model) + "\n\n")
        buf.write("KEY SIDE — retrieved chunks\n")
        for i, h in enumerate(key_hits[:top_n]):
            raw = h.get("similarity")
            buf.write(
                f"[{i + 1}] score={_hit_score(h):.4f}"
                f"{f' sim={float(raw):.4f}' if raw is not None else ''}\n"
            )
            buf.write(_normalize_display_text(h.get("text_content") or "") + "\n\n")
        buf.write("STUDENT SIDE — raw OCR\n")
        buf.write(_normalize_display_text(raw_ocr) + "\n\n")
        buf.write(f"STUDENT SIDE — after {format_method}\n")
        buf.write(_normalize_display_text(formatted_student) + "\n\n")
        buf.write("STUDENT SIDE — retrieved chunks\n")
        for i, h in enumerate(sheet_hits[:top_n]):
            meta = h.get("meta") or {}
            raw = h.get("similarity")
            buf.write(
                f"[{i + 1}] score={_hit_score(h):.4f}"
                f"{f' sim={float(raw):.4f}' if raw is not None else ''} "
                f"region={meta.get('region_id')}\n"
            )
            buf.write(_normalize_display_text(h.get("text_content") or "") + "\n\n")
        with _comparison_out_path.open("a", encoding="utf-8") as f:
            f.write(buf.getvalue())


def print_retrieval_hits(
    label: str,
    hits: List[Dict[str, Any]],
    *,
    top_n: int,
) -> None:
    print(f"\n    --- {label} ({len(hits)} hit(s)) ---")
    for rank, h in enumerate(hits[:top_n]):
        meta = h.get("meta") or {}
        kind = meta.get("kind") or ("key" if str(h.get("document_id", "")).startswith("keys_") else "sheet")
        score = _hit_score(h)
        raw = h.get("similarity")
        raw_s = f" sim={float(raw):.4f}" if raw is not None else ""
        dist = h.get("vector_distance", h.get("distance"))
        dist_s = f" dist={float(dist):.4f}" if dist is not None else ""
        print(
            f"      #{rank + 1} [{kind}] score={score:.4f}{raw_s}{dist_s} "
            f"chunk={h.get('chunk_id')} q={meta.get('question_id') or '-'} "
            f"region={meta.get('region_id') or '-'}"
        )
        print(f"         {_short(h.get('text_content') or '', 90)}")


def run_ingestion(exam_id: str, sheet_id: str, *, force: bool) -> Dict[str, Any]:
    from autograder.rag.ingest import ingest_keys_rag, ingest_sheet_rag, keys_document_id, sheet_document_id

    print("\n=== RAG ingestion ===")
    keys_out = ingest_keys_rag(exam_id, force=force)
    print(f"  keys: {json.dumps(keys_out, default=str)}")
    sheet_out = ingest_sheet_rag(sheet_id, force=force)
    print(f"  sheet: {json.dumps(sheet_out, default=str)}")

    key_doc = keys_document_id(exam_id)
    sheet_doc = sheet_document_id(sheet_id)
    key_n = count_rag_chunks_for_document(key_doc)
    sheet_n = count_rag_chunks_for_document(sheet_doc)
    print(f"  rag_chunks count: {key_doc}={key_n}, {sheet_doc}={sheet_n}")

    ok = keys_out.get("status") in ("success", "cached") and sheet_out.get("status") in (
        "success",
        "cached",
    )
    if key_n < 1:
        _warn(f"No chunks in rag_chunks for {key_doc}")
        ok = False
    if sheet_n < 1:
        _warn(f"No chunks in rag_chunks for {sheet_doc}")
        ok = False
    if ok:
        _ok("Ingestion wrote or refreshed both corpora")
    return {"keys": keys_out, "sheet": sheet_out, "key_chunks": key_n, "sheet_chunks": sheet_n}


def test_per_answer_retrieval(
    exam_id: str,
    sheet_id: str,
    *,
    top_k: int,
    format_llm: bool,
    heuristic_only: bool,
    max_regions: int,
    show_comparison: bool = False,
    verbose_hits: bool = False,
    bounded_compare: bool = False,
    regions_per_page: Optional[List[int]] = None,
) -> int:
    from autograder.db import database_status, get_rag_chunks_for_sheet, get_sheet, list_answer_keys
    from autograder.embeddings import embed_text_local
    from autograder.rag.ingest import keys_document_id, sheet_document_id
    from autograder.db import search_rag_chunks
    from autograder.rag.retrieval import match_answer_key, retrieve_context_for_grading
    from autograder.rag.retrieval import _key_corpus_query, _sheet_corpus_query
    from autograder.rag.boundaries import evaluate_all_questions, evaluate_bounded_pair
    from autograder.text_format import format_student_answer

    mode = "bounded per-question (LLM format)" if bounded_compare else "format → hybrid RAG"
    print(f"\n=== Per-answer retrieval ({mode}) ===")
    keys = list_answer_keys(exam_id)
    if not keys:
        _fail(f"No answer keys for exam_id={exam_id!r}")
        return 1

    keys_by_id = {str(k["id"]): k for k in keys}
    sheet_chunks = get_rag_chunks_for_sheet(sheet_id, limit=500)
    regions = regions_from_sheet_chunks(sheet_chunks)
    if not regions:
        _fail("No sheet regions in rag_chunks — run with --ingest or re-upload the sheet")
        return 1

    link_errors: List[str] = []
    tested = 0

    if bounded_compare and regions_per_page and len(regions) != len(keys):
        _warn(
            f"Sheet has {len(regions)} region(s) but layout expects {sum(regions_per_page)} "
            f"({regions_per_page}) — run --reingest-sheet to align OCR strips with answers"
        )

    if bounded_compare:
        use_llm = format_llm and not heuristic_only
        if not use_llm:
            _warn("bounded-compare: use --format-llm for accurate LLM OCR cleanup (heuristic only)")
        if regions_per_page:
            print(f"  Layout: regions_per_page={regions_per_page} (positional 1:1 when count matches keys)")
        evaluations = evaluate_all_questions(
            exam_id=exam_id,
            sheet_id=sheet_id,
            keys=keys,
            regions=regions,
            format_llm=use_llm,
            heuristic_only=heuristic_only,
            regions_per_page=regions_per_page,
        )
        if max_regions > 0:
            evaluations = evaluations[:max_regions]
        for ev in evaluations:
            print_bounded_evaluation(ev)
            for sp in ev.key.chunk_spans:
                ok_link, errs = verify_chunk_database_links(
                    str(sp.chunk_id),
                    exam_id=exam_id,
                    sheet_id=sheet_id,
                    keys_by_id=keys_by_id,
                )
                if not ok_link:
                    link_errors.extend(errs)
            for sp in ev.sheet_raw.chunk_spans:
                ok_link, errs = verify_chunk_database_links(
                    str(sp.chunk_id),
                    exam_id=exam_id,
                    sheet_id=sheet_id,
                    keys_by_id=keys_by_id,
                )
                if not ok_link:
                    link_errors.extend(errs)
            tested += 1
            _ok(f"Graded {ev.question_id} via {ev.region_id} ({ev.format_method})")
    else:
        region_list = regions[:max_regions] if max_regions > 0 else regions
        for region_index, reg in enumerate(region_list):
            raw_ocr = reg.get("text") or ""
            if not raw_ocr.strip():
                _warn(f"Region {reg.get('region_id')}: empty OCR text, skipping")
                continue

            chosen = match_answer_key(region_index, raw_ocr, keys, top_k=top_k)
            qid = str(chosen.get("question_id") or "?")

            formatted = format_student_answer(
                raw_ocr,
                chosen,
                force_heuristic=heuristic_only or not format_llm,
            )
            student_text = formatted.formatted

            if not show_comparison:
                print(f"\n  Region {region_index} ({reg.get('region_id')}) → key {qid}")
                print(f"    format: method={formatted.method} flags={formatted.flags}")
                print(f"    raw OCR:    {_short(raw_ocr, 80)}")
                print(f"    formatted:  {_short(student_text, 80)}")

            ctx = retrieve_context_for_grading(
                sheet_id,
                exam_id,
                student_text,
                chosen,
                top_k=top_k,
                region_index=region_index,
            )

            key_hits = ctx.get("key_hits") or []
            sheet_hits = ctx.get("sheet_hits") or []

            if show_comparison:
                print_side_by_side_comparison(
                    question_id=qid,
                    region_id=str(reg.get("region_id") or "?"),
                    region_index=region_index,
                    key=chosen,
                    raw_ocr=raw_ocr,
                    formatted_student=student_text,
                    format_method=formatted.method,
                    key_hits=key_hits,
                    sheet_hits=sheet_hits,
                    top_n=top_k,
                )
            elif verbose_hits:
                print_retrieval_hits("Answer-key corpus (hybrid)", key_hits, top_n=top_k)
                print_retrieval_hits("Sheet corpus (hybrid)", sheet_hits, top_n=top_k)
                key_q = _key_corpus_query(chosen)
                sheet_q = _sheet_corpus_query(student_text, chosen)
                vec_key = search_rag_chunks(
                    embed_text_local(key_q),
                    top_k=top_k,
                    document_id=keys_document_id(exam_id),
                )
                vec_sheet = search_rag_chunks(
                    embed_text_local(sheet_q),
                    top_k=top_k,
                    document_id=sheet_document_id(sheet_id),
                )
                print_retrieval_hits("Answer-key corpus (vector ANN)", vec_key, top_n=min(3, top_k))
                print_retrieval_hits("Sheet corpus (vector ANN)", vec_sheet, top_n=min(3, top_k))

            if ctx.get("chunk_ids") and not show_comparison:
                print(f"    context chunk_ids ({len(ctx['chunk_ids'])}): {', '.join(ctx['chunk_ids'][:8])}")
                if len(ctx["chunk_ids"]) > 8:
                    print(f"      … +{len(ctx['chunk_ids']) - 8} more")
            if "KEY SIDE" in (ctx.get("context_text") or ""):
                _ok(f"Grading context built for {qid}")
            else:
                _warn(f"Grading context missing KEY/STUDENT sides for {qid}")

            for cid in ctx.get("chunk_ids") or []:
                ok_link, errs = verify_chunk_database_links(
                    str(cid),
                    exam_id=exam_id,
                    sheet_id=sheet_id,
                    keys_by_id=keys_by_id,
                )
                if not ok_link:
                    link_errors.extend(errs)

            tested += 1

    print("\n=== Database linkage summary ===")
    sheet_row = get_sheet(sheet_id)
    if not sheet_row:
        _fail(f"sheets.id={sheet_id!r} not found")
        return 1
    if str(sheet_row.get("exam_id") or "") != exam_id:
        _fail(f"Sheet exam_id={sheet_row.get('exam_id')!r} != {exam_id!r}")
        return 1
    _ok(f"Sheet {sheet_id[:12]}… → exam_id={exam_id}")

    st = database_status()
    print(
        f"  DB: connected={st.get('connected')} rag_ready={st.get('rag_ready')} "
        f"rag_chunks≈{st.get('counts', {}).get('rag_chunks', '?')}"
    )

    if link_errors:
        for e in link_errors[:20]:
            _fail(e)
        if len(link_errors) > 20:
            print(f"  … +{len(link_errors) - 20} more linkage errors")
        return 1

    _ok(f"All {tested} region(s): retrieved chunks exist and link to exam/sheet/keys")
    return 0


def _pick_exam_with_keys_and_sheet(
    exams: List[Dict[str, Any]],
    all_sheets: List[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[str]]:
    """Prefer an exam that has both answer keys and at least one linked sheet."""
    sheets_by_exam: Dict[str, List[Dict[str, Any]]] = {}
    for s in all_sheets:
        ex = str(s.get("exam_id") or "").strip()
        if ex:
            sheets_by_exam.setdefault(ex, []).append(s)

    from autograder.db import list_answer_keys

    for e in exams:
        ex = str(e.get("exam_id") or "").strip()
        if not ex:
            continue
        if int(e.get("key_count") or 0) > 0 and sheets_by_exam.get(ex):
            return ex, str(sheets_by_exam[ex][0].get("id") or "")

    for e in exams:
        ex = str(e.get("exam_id") or "").strip()
        if not ex:
            continue
        if list_answer_keys(ex) and sheets_by_exam.get(ex):
            return ex, str(sheets_by_exam[ex][0].get("id") or "")

    return None, None


def resolve_exam_and_sheet(
    exam_id: Optional[str],
    sheet_id: Optional[str],
) -> Tuple[Optional[str], Optional[str], int]:
    from autograder.db import database_status, get_sheet, list_answer_keys, list_exams_with_counts, list_sheets

    print("=== GRADE RAG ingestion + retrieval test ===\n")
    st = database_status()
    if not st.get("connected"):
        _fail(st.get("error") or "Database not connected")
        return None, None, 1
    _ok(f"Postgres connected (rag_ready={st.get('rag_ready')})")

    all_sheets = list_sheets(limit=50)
    target_exam = exam_id
    target_sheet = sheet_id

    if not target_exam:
        exams = list_exams_with_counts(limit=20)
        if not exams:
            _fail("No exams in database — upload keys + sheet first")
            return None, None, 1
        picked_ex, picked_sh = _pick_exam_with_keys_and_sheet(exams, all_sheets)
        if picked_ex and picked_sh:
            target_exam, target_sheet = picked_ex, picked_sh
            print(f"  Using exam with keys + sheet: {target_exam}")
        else:
            target_exam = str(exams[0].get("exam_id") or "")
            print(f"  Using latest exam (may lack keys): {target_exam}")

    if not target_sheet:
        sheets = [s for s in all_sheets if str(s.get("exam_id") or "") == target_exam]
        if not sheets:
            _fail(f"No sheets for exam_id={target_exam!r}")
            return None, None, 1
        target_sheet = str(sheets[0].get("id") or "")
        print(f"  Using first sheet: {target_sheet}")

    if not list_answer_keys(target_exam):
        _fail(
            f"No answer keys for exam_id={target_exam!r}. "
            "Upload keys or pass --exam-id for an exam that has keys."
        )
        return None, None, 1

    row = get_sheet(target_sheet)
    if not row:
        _fail(f"sheet_id not found: {target_sheet}")
        return None, None, 1
    if str(row.get("exam_id") or "") != target_exam:
        _fail(f"Sheet linked to {row.get('exam_id')!r}, not {target_exam!r}")
        return None, None, 1

    return target_exam, target_sheet, 0


def _resolve_pdf_path(path_arg: str) -> Path:
    p = Path(path_arg)
    if not p.is_absolute():
        p = (_repo_root() / p).resolve()
    if p.is_file():
        return p
    # Glob for DocScanner-style names with special spaces
    parent = p.parent if p.parent != Path(".") else _repo_root()
    matches = sorted(parent.glob(p.name))
    if not matches and "*" not in p.name:
        matches = sorted(parent.glob(f"*{p.stem}*"))
    if matches:
        return matches[0].resolve()
    raise FileNotFoundError(f"PDF not found: {path_arg}")


# CIE corpus: docx keys under cie/keys/ paired with scanned sheets under cie/sheets/
# Optional 4th element: grid rows per PDF page (1:1 with answer keys when sum == question count).
# cie-daa: page1=Q1–Q3 (3 strips); Q4–Q6 are multipart (a)+(b) in one strip each → 3+1+1+1.
CIE_BUNDLES: List[Tuple[str, str, str, Optional[List[int]]]] = [
    (
        "cie-daa",
        "cie/keys/DAA.docx",
        "cie/sheets/DESIGN AND ANALYSIS OF ALGORITHM(DAA).pdf",
        [3, 1, 1, 1],
    ),
    ("cie-ml", "cie/keys/ML.docx", "cie/sheets/MACHINE LEARNING.pdf", None),
    ("cie-dism", "cie/keys/DISM.docx", "cie/sheets/DISASTER MITIGATION.pdf", None),
    ("cie-compiler", "cie/keys/compiler design.docx", "cie/sheets/COMPILER DESIGN.pdf", None),
    ("cie-dm", "cie/keys/data mining.docx", "cie/sheets/DATA MINING.pdf", None),
    (
        "cie-crypto",
        "cie/keys/cryptography.docx",
        "cie/sheets/CRYPTOGRAPHY AND NETWORK SECURITY.pdf",
        None,
    ),
]


def _bundle_sheet_regions(bundle: Tuple[str, ...]) -> Optional[List[int]]:
    return bundle[3] if len(bundle) > 3 else None


def find_ingested_exam(exam_id: str) -> Optional[Tuple[str, str]]:
    """Return (exam_id, sheet_id) when keys + key/sheet RAG chunks already exist."""
    from autograder.db import get_rag_chunks_for_sheet, list_answer_keys, list_sheets
    from autograder.rag.ingest import keys_document_id

    keys = list_answer_keys(exam_id)
    if not keys:
        return None
    if count_rag_chunks_for_document(keys_document_id(exam_id)) < 1:
        return None
    for s in list_sheets(limit=100):
        if str(s.get("exam_id") or "") != exam_id:
            continue
        sid = str(s.get("id") or "")
        if get_rag_chunks_for_sheet(sid, limit=1):
            return exam_id, sid
    return None


def _upload_key_sheet_bundle(
    payload,
    sheet_pdf: Path,
    *,
    exam_id: str,
    label: str,
    force_ingest: bool = True,
) -> Tuple[str, str]:
    """Insert keys + sheet, ingest RAG; shared by PDF/DOCX bundle runners."""
    import shutil
    import uuid

    from autograder.db import (
        delete_answer_keys_for_exam,
        delete_rag_chunks_for_document,
        insert_answer_key,
        insert_sheet,
        list_answer_keys,
        next_answer_key_sort_order_start,
    )
    from autograder.rag.ingest import ingest_keys_rag, ingest_sheet_rag, keys_document_id

    ex = exam_id.strip()
    print(f"\n=== {label} ===")
    print(f"  exam_id={ex}")

    if force_ingest:
        delete_answer_keys_for_exam(ex)
        delete_rag_chunks_for_document(keys_document_id(ex))

    if not payload.questions:
        raise ValueError(f"No questions parsed for {ex}")

    sort_base = next_answer_key_sort_order_start(ex)
    for i, q in enumerate(payload.questions):
        kid = insert_answer_key(
            ex,
            q.question_id,
            q.expected_answer,
            None,
            q.max_marks,
            q.domain,
            q.rubric_override,
            sort_order=sort_base + i,
        )
        if i < 3:
            preview = _short(q.expected_answer, 50)
            print(f"  key {q.question_id} ({q.max_marks}m): {preview}")

    _ok(f"Inserted {len(payload.questions)} answer key(s)")

    upload_dir = _repo_root() / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"sheet_{uuid.uuid4().hex[:8]}{sheet_pdf.suffix.lower()}"
    shutil.copy2(sheet_pdf, dest)
    sheet_id = insert_sheet(sheet_pdf.name, str(dest.resolve()), exam_id=ex)
    _ok(f"Sheet {sheet_id[:12]}… ← {sheet_pdf.name}")

    keys_ingest = ingest_keys_rag(ex, force=force_ingest)
    print(f"  keys ingest: {json.dumps(keys_ingest, default=str)}")
    sheet_ingest = ingest_sheet_rag(sheet_id, force=force_ingest)
    print(f"  sheet ingest: {json.dumps(sheet_ingest, default=str)}")

    if sheet_ingest.get("status") not in ("success", "cached"):
        raise RuntimeError(f"Sheet RAG ingest failed: {sheet_ingest}")
    if not list_answer_keys(ex):
        raise RuntimeError("No answer keys after upload")

    return ex, sheet_id


def run_cie_bundle(
    exam_slug: str,
    key_docx: Path,
    sheet_pdf: Path,
    *,
    default_max_marks: float = 4.0,
    force_ingest: bool = True,
) -> Tuple[str, str]:
    from autograder.key_docx import docx_path_to_upload_request

    payload = docx_path_to_upload_request(key_docx, exam_slug, default_max_marks)
    return _upload_key_sheet_bundle(
        payload,
        sheet_pdf,
        exam_id=exam_slug,
        label=f"CIE bundle ({key_docx.name} + {sheet_pdf.name})",
        force_ingest=force_ingest,
    )


def _parse_regions_per_page(spec: Optional[str]) -> Optional[List[int]]:
    if not spec or not str(spec).strip():
        return None
    out: List[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        n = int(part)
        if n < 1:
            raise ValueError(f"regions per page must be >= 1, got {n!r}")
        out.append(n)
    return out or None


def reingest_sheet_regions(
    sheet_id: str,
    *,
    regions_per_page: Optional[List[int]] = None,
    expected_num_regions: Optional[int] = None,
) -> Dict[str, Any]:
    """Re-OCR an existing sheet with grid/contour segmentation (per-page row counts)."""
    from autograder.rag.ingest import ingest_sheet_rag

    print(f"\n=== Re-ingest sheet {sheet_id[:12]}… (segmented OCR) ===")
    if regions_per_page:
        print(f"  regions_per_page={regions_per_page}")
    elif expected_num_regions:
        print(f"  expected_num_regions={expected_num_regions} per page")
    result = ingest_sheet_rag(
        sheet_id,
        force=True,
        full_page=False,
        regions_per_page=regions_per_page,
        expected_num_regions=expected_num_regions,
    )
    print(f"  sheet ingest: {json.dumps(result, default=str)}")
    if result.get("status") not in ("success", "cached"):
        raise RuntimeError(f"Sheet re-ingest failed: {result}")
    return result


def resolve_cie_exam(
    exam_slug: str,
    key_docx: Path,
    sheet_pdf: Path,
    *,
    retrieve_only: bool,
    reuse: bool,
    force_ingest: bool,
    default_max_marks: float,
    reingest_sheet: bool = False,
    regions_per_page: Optional[List[int]] = None,
    expected_num_regions: Optional[int] = None,
) -> Tuple[str, str]:
    """Reuse DB rows when possible; skip slow sheet OCR on repeat runs."""
    found = find_ingested_exam(exam_slug)
    if reingest_sheet:
        if not found:
            raise RuntimeError(
                f"{exam_slug} not indexed yet — run a full ingest first, then --reingest-sheet"
            )
        exam_id, sheet_id = found
        reingest_sheet_regions(
            sheet_id,
            regions_per_page=regions_per_page,
            expected_num_regions=expected_num_regions,
        )
        return exam_id, sheet_id
    if retrieve_only:
        if not found:
            raise RuntimeError(
                f"{exam_slug} not indexed yet — run once without --retrieve-only "
                f"(first run OCRs each sheet PDF and takes several minutes per exam)"
            )
        _ok(f"Retrieve-only: reusing {exam_slug} sheet {found[1][:12]}…")
        return found
    if reuse and found:
        _ok(f"Reusing indexed {exam_slug} (skip upload + OCR)")
        return found
    return run_cie_bundle(
        exam_slug,
        key_docx,
        sheet_pdf,
        default_max_marks=default_max_marks,
        force_ingest=force_ingest,
    )


def run_pdf_bundle(
    key_pdf: Path,
    sheet_pdf: Path,
    *,
    exam_id: str,
    default_max_marks: float = 4.0,
    cleanup: bool,
) -> Tuple[str, str]:
    """
    Upload Key.pdf + student sheet PDF, ingest both RAG corpora, return (exam_id, sheet_id).
    """
    import uuid

    from autograder.key_pdf import pdf_bytes_to_upload_request

    ex = exam_id.strip() or f"pdf-rag-{uuid.uuid4().hex[:8]}"
    payload = pdf_bytes_to_upload_request(key_pdf.read_bytes(), ex, default_max_marks)
    sheet_id_pair = _upload_key_sheet_bundle(
        payload,
        sheet_pdf,
        exam_id=ex,
        label=f"PDF bundle ({key_pdf.name} + {sheet_pdf.name})",
    )
    if cleanup:
        print("  (fixture kept until test ends; use --no-cleanup to persist)")
    return sheet_id_pair


def _cleanup_pdf_bundle(exam_id: str, sheet_id: str) -> None:
    _cleanup_smoke(exam_id, sheet_id)


def run_smoke_fixture(*, cleanup: bool) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Insert a minimal exam + key + sheet row and seed rag_chunks for retrieval tests.

    Returns (exam_id, sheet_id, cleanup_ids).
    """
    import uuid

    from autograder.db import insert_answer_key, insert_sheet, upsert_rag_chunks_batch
    from autograder.embeddings import embed_text_local
    from autograder.rag.ingest import ingest_keys_rag, sheet_document_id

    exam_id = f"__rag_test__{uuid.uuid4().hex[:10]}"
    vec = embed_text_local(
        "Photosynthesis converts light energy into chemical energy in chloroplasts."
    )
    key_id = insert_answer_key(
        exam_id,
        "Q1",
        "Photosynthesis converts light energy into chemical energy in chloroplasts.",
        vec,
        4.0,
        "biology",
        None,
        sort_order=0,
    )
    sheet_id = insert_sheet(
        "rag_smoke_sheet.png",
        str(_repo_root() / "extraction.json"),
        exam_id=exam_id,
    )

    # If sheet file missing, seed sheet corpus directly from key-like student text
    sheet_doc = sheet_document_id(sheet_id)
    student_stub = "Student explains chloroplasts capture sunlight for energy storage"
    rows = [
        {
            "chunk_id": f"{sheet_doc}_r0",
            "document_id": sheet_doc,
            "chunk_index": 0,
            "text_content": student_stub,
            "embedding": embed_text_local(student_stub),
            "meta": {
                "kind": "sheet",
                "sheet_id": sheet_id,
                "exam_id": exam_id,
                "region_id": "R1",
                "source_page": 1,
            },
        }
    ]
    upsert_rag_chunks_batch(rows)
    ingest_keys_rag(exam_id, force=True)

    cleanup_ids = [exam_id, sheet_id, key_id]
    print(f"\n=== Smoke fixture ===")
    _ok(f"exam_id={exam_id} sheet_id={sheet_id} key_id={key_id}")
    if not cleanup:
        print("  (--no-cleanup: rows left in DB)")

    return exam_id, sheet_id, cleanup_ids


def _cleanup_smoke(exam_id: str, sheet_id: str) -> None:
    from autograder.db import _pg_connect, _pg_execute, delete_rag_chunks_for_document
    from autograder.rag.ingest import keys_document_id, sheet_document_id

    delete_rag_chunks_for_document(keys_document_id(exam_id))
    delete_rag_chunks_for_document(sheet_document_id(sheet_id))
    with _pg_connect() as conn:
        with conn.cursor() as cur:
            _pg_execute(cur, "DELETE FROM public.answer_keys WHERE exam_id = %s", (exam_id,))
            _pg_execute(cur, "DELETE FROM public.sheets WHERE id = %s", (sheet_id,))
        conn.commit()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    _load_dotenv()
    os.chdir(_repo_root())
    if not os.environ.get("PYTHONPATH"):
        sys.path.insert(0, str(_repo_root() / "src"))

    parser = argparse.ArgumentParser(
        description="Test RAG ingest + per-answer retrieval with DB linkage checks"
    )
    parser.add_argument("--exam-id", help="Exam id (default: latest in DB)")
    parser.add_argument("--sheet-id", help="Sheet UUID (default: first sheet for exam)")
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Re-run ingest_keys_rag + ingest_sheet_rag before retrieval tests",
    )
    parser.add_argument("--top-k", type=int, default=3, help="Retrieval top-k (default: 3)")
    parser.add_argument(
        "--max-regions",
        type=int,
        default=0,
        help="Limit regions tested (0 = all indexed regions)",
    )
    parser.add_argument(
        "--format-llm",
        action="store_true",
        help="Use LLM OCR formatting (GRADE_OCR_FORMAT_LLM / GRADE_ENABLE_LLM); needs API keys",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Print full KEY vs STUDENT side-by-side text (use with --format-llm)",
    )
    parser.add_argument(
        "--verbose-hits",
        action="store_true",
        help="Show hybrid/vector hit tables (default when --compare is off)",
    )
    parser.add_argument(
        "--compare-out",
        type=str,
        default=None,
        help="Write comparison panels to this text file (e.g. data/rag_comparison.txt)",
    )
    parser.add_argument(
        "--heuristic-only",
        action="store_true",
        help="Skip LLM formatting even if --format-llm is set",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Create temporary exam/key/sheet + RAG rows, run tests, then delete",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="With --smoke / --key-pdf, leave fixture rows in the database",
    )
    parser.add_argument(
        "--key-pdf",
        type=str,
        help="Answer key PDF (e.g. Key.pdf); requires --sheet-pdf",
    )
    parser.add_argument(
        "--sheet-pdf",
        type=str,
        help="Student answer sheet PDF (e.g. DocScanner … am.pdf)",
    )
    parser.add_argument(
        "--pdf-exam-id",
        type=str,
        default="key-docscanner-test",
        help="exam_id when using --key-pdf + --sheet-pdf (default: key-docscanner-test)",
    )
    parser.add_argument(
        "--default-max-marks",
        type=float,
        default=4.0,
        help="Default max marks per key question from PDF (default: 4)",
    )
    parser.add_argument(
        "--cie",
        action="store_true",
        help="Ingest + retrieve all cie/keys/*.docx + cie/sheets/*.pdf pairs",
    )
    parser.add_argument(
        "--cie-exam",
        type=str,
        default=None,
        help="Run one CIE slug only (e.g. cie-daa, cie-ml); use with or without --cie",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Reuse indexed exams, skip LLM OCR format, cap regions (quick re-test)",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Skip upload/OCR when exam already has keys + sheet RAG chunks in DB",
    )
    parser.add_argument(
        "--retrieve-only",
        action="store_true",
        help="Never ingest; only retrieval/format on data already in DB (fastest)",
    )
    parser.add_argument(
        "--bounded-compare",
        action="store_true",
        help="Assemble ALL in-scope key/sheet chunks with start/end boundaries + score",
    )
    parser.add_argument(
        "--reingest-sheet",
        action="store_true",
        help="Re-OCR existing sheet with segmentation (use with --sheet-regions)",
    )
    parser.add_argument(
        "--sheet-regions",
        type=str,
        default=None,
        help="Comma-separated grid rows per PDF page, e.g. 3,6 for 9 regions on 2 pages",
    )
    args = parser.parse_args()

    if args.fast:
        args.reuse = True
        if args.format_llm:
            _warn("--fast ignores --format-llm (heuristic format only)")
            args.format_llm = False
        if args.max_regions == 0 and not args.bounded_compare:
            args.max_regions = 2
        if args.top_k == 3:
            args.top_k = 2
    if args.reingest_sheet:
        args.retrieve_only = False
    global _comparison_out_path
    _comparison_out_path = None

    if not _database_url():
        print(
            "[fail] Set GRADE_DATABASE_URL or DATABASE_URL (see .env.example)",
            file=sys.stderr,
        )
        return 1

    try:
        import psycopg  # noqa: F401
        import pgvector  # noqa: F401
    except ImportError:
        print('[fail] pip install -e ".[postgres]"', file=sys.stderr)
        return 1

    from autograder.db import init_db

    try:
        init_db()
    except Exception as e:
        _fail(f"init_db(): {e}")
        return 1

    pdf_bundle = bool(args.key_pdf or args.sheet_pdf)
    cie_mode = bool(args.cie or args.cie_exam)
    if pdf_bundle and not (args.key_pdf and args.sheet_pdf):
        print("[fail] --key-pdf and --sheet-pdf must be used together", file=sys.stderr)
        return 1
    if sum([pdf_bundle, args.smoke, cie_mode]) > 1:
        print("[fail] Use only one of --smoke, --key-pdf/--sheet-pdf, or --cie", file=sys.stderr)
        return 1

    if args.bounded_compare and not args.heuristic_only:
        args.format_llm = True
    show_comparison = args.compare or args.format_llm
    if show_comparison and not args.format_llm and not args.bounded_compare:
        _warn("--compare without --format-llm: student text uses heuristic formatting only")

    if cie_mode:
        bundles = CIE_BUNDLES
        if args.cie_exam:
            bundles = [b for b in CIE_BUNDLES if b[0] == args.cie_exam]
            if not bundles:
                print(f"[fail] Unknown --cie-exam {args.cie_exam!r}. Choices: {[b[0] for b in CIE_BUNDLES]}", file=sys.stderr)
                return 1
        compare_path = args.compare_out or "data/cie_rag_comparison.txt"
        out_p = Path(compare_path)
        if not out_p.is_absolute():
            out_p = _repo_root() / out_p
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text("GRADE CIE RAG — ingestion + LLM format + retrieval\n", encoding="utf-8")
        _comparison_out_path = out_p
        print(f"=== CIE batch ({len(bundles)} exam(s)) ===\n")
        print(f"  Output: {out_p}")

        if args.retrieve_only or args.reuse:
            print("  Mode: reuse indexed data (no sheet OCR unless first-time ingest)\n")
        elif not args.fast:
            print(
                "  Tip: first run OCRs every sheet page (slow). "
                "After that use --fast or --retrieve-only.\n"
            )

        failures = 0
        force_ingest = not (args.reuse or args.retrieve_only or args.fast or args.reingest_sheet)
        try:
            regions_per_page = _parse_regions_per_page(args.sheet_regions)
        except ValueError as e:
            _fail(str(e))
            return 1
        for bundle in bundles:
            slug, key_rel, sheet_rel = bundle[0], bundle[1], bundle[2]
            layout = regions_per_page or _bundle_sheet_regions(bundle)
            key_path = (_repo_root() / key_rel).resolve()
            sheet_path = (_repo_root() / sheet_rel).resolve()
            if not key_path.is_file() or not sheet_path.is_file():
                _fail(f"Missing files for {slug}: {key_path} / {sheet_path}")
                failures += 1
                continue
            if layout and not args.sheet_regions:
                print(f"  [{slug}] answer layout: {layout} rows/page (reference regions)")
            try:
                exam_id, sheet_id = resolve_cie_exam(
                    slug,
                    key_path,
                    sheet_path,
                    retrieve_only=args.retrieve_only,
                    reuse=args.reuse,
                    force_ingest=force_ingest,
                    default_max_marks=args.default_max_marks,
                    reingest_sheet=args.reingest_sheet,
                    regions_per_page=layout,
                )
            except Exception as e:
                _fail(f"{slug} failed: {e}")
                failures += 1
                continue
            with out_p.open("a", encoding="utf-8") as f:
                f.write(f"\n\n########## {slug} exam={exam_id} sheet={sheet_id} ##########\n")
            code = test_per_answer_retrieval(
                exam_id,
                sheet_id,
                top_k=max(1, min(20, args.top_k)),
                format_llm=args.format_llm,
                heuristic_only=args.heuristic_only,
                max_regions=max(0, args.max_regions),
                show_comparison=show_comparison and not args.bounded_compare,
                verbose_hits=args.verbose_hits or not (show_comparison or args.bounded_compare),
                bounded_compare=args.bounded_compare,
                regions_per_page=layout,
            )
            if code != 0:
                failures += 1
        if failures:
            _fail(f"{failures} CIE exam(s) failed")
            return 1
        _ok(f"All {len(bundles)} CIE exam(s) passed")
        _ok(f"Comparison saved to {out_p}")
        return 0

    use_pdf_cleanup = False
    smoke_cleanup: List[str] = []
    if pdf_bundle:
        try:
            key_path = _resolve_pdf_path(args.key_pdf)
            sheet_path = _resolve_pdf_path(args.sheet_pdf)
            exam_id, sheet_id = run_pdf_bundle(
                key_path,
                sheet_path,
                exam_id=args.pdf_exam_id,
                default_max_marks=args.default_max_marks,
                cleanup=not args.no_cleanup,
            )
            use_pdf_cleanup = not args.no_cleanup
        except Exception as e:
            _fail(f"PDF bundle failed: {e}")
            return 1
    elif args.smoke:
        try:
            exam_id, sheet_id, smoke_cleanup = run_smoke_fixture(cleanup=not args.no_cleanup)
        except Exception as e:
            _fail(f"Smoke fixture failed: {e}")
            return 1
        if not exam_id or not sheet_id:
            return 1
    else:
        exam_id, sheet_id, code = resolve_exam_and_sheet(args.exam_id, args.sheet_id)
        if code != 0 or not exam_id or not sheet_id:
            return code or 1

    if args.ingest and not pdf_bundle:
        try:
            run_ingestion(exam_id, sheet_id, force=True)
        except Exception as e:
            _fail(f"Ingestion failed: {e}")
            return 1

    if args.compare_out:
        out_p = Path(args.compare_out)
        if not out_p.is_absolute():
            out_p = _repo_root() / out_p
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(
            f"GRADE RAG comparison — exam={exam_id} sheet={sheet_id}\n",
            encoding="utf-8",
        )
        _comparison_out_path = out_p
        print(f"\n  Writing comparisons to {out_p}")

    code = test_per_answer_retrieval(
        exam_id,
        sheet_id,
        top_k=max(1, min(20, args.top_k)),
        format_llm=args.format_llm,
        heuristic_only=args.heuristic_only,
        max_regions=max(0, args.max_regions),
        show_comparison=show_comparison and not args.bounded_compare,
        verbose_hits=args.verbose_hits or not (show_comparison or args.bounded_compare),
        bounded_compare=args.bounded_compare,
    )

    if args.smoke and smoke_cleanup and not args.no_cleanup:
        try:
            _cleanup_smoke(exam_id, sheet_id)
            _ok("Smoke fixture cleaned up")
        except Exception as e:
            _warn(f"Smoke cleanup failed: {e}")

    if use_pdf_cleanup:
        try:
            _cleanup_pdf_bundle(exam_id, sheet_id)
            _ok("PDF bundle fixture cleaned up")
        except Exception as e:
            _warn(f"PDF bundle cleanup failed: {e}")

    if _comparison_out_path is not None:
        _ok(f"Comparison saved to {_comparison_out_path}")

    return code


if __name__ == "__main__":
    sys.exit(main())
