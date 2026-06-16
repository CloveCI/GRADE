"""
Ingest uploaded answer sheets into ``public.rag_chunks`` (GRADE 128-D + pgvector).

Adapted from ``processing/embedder.py``: chunk → batch embed → upsert, scoped per sheet via ``document_id``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ProgressCallback = Callable[[int, int], None]

from autograder.db import (
    delete_rag_chunks_for_document,
    get_rag_chunks_for_sheet,
    get_sheet,
    list_answer_keys,
    list_sheet_question_answers,
    update_sheet_question_regions,
    upsert_sheet_question_answers,
    upsert_rag_chunks_batch,
)
from autograder.exam_layouts import resolve_regions_per_page
from autograder.embeddings import embed_texts_batch
from autograder.ocr import ocr_patch
from autograder.preprocessing import preprocess_options_from_env, preprocess_sheet_for_evaluation
from autograder.rag_extract import build_rag_payload, rag_rows_for_postgres

logger = logging.getLogger(__name__)


def sheet_document_id(sheet_id: str) -> str:
    """Stable RAG document id for a sheet row (used in ``rag_chunks.document_id``)."""
    return f"sheet_{sheet_id}"


def keys_document_id(exam_id: str) -> str:
    """RAG corpus id for all answer keys of one exam (paired with sheets via ``meta.exam_id``)."""
    return f"keys_{exam_id}"


def exam_rag_document_ids(exam_id: str, sheet_id: str) -> List[str]:
    """Document ids searched together during grading for one exam + sheet."""
    return [keys_document_id(exam_id), sheet_document_id(sheet_id)]


def ingest_keys_rag(exam_id: str, *, force: bool = True) -> Dict[str, Any]:
    """
    Mirror ``answer_keys`` rows into ``rag_chunks`` so hybrid search can retrieve
    model answers alongside sheet OCR chunks under the same ``exam_id``.
    """
    keys = list_answer_keys(exam_id)
    if not keys:
        return {"status": "skipped", "reason": "no_keys", "exam_id": exam_id}

    document_id = keys_document_id(exam_id)
    if force:
        delete_rag_chunks_for_document(document_id)

    rows: List[Dict[str, Any]] = []
    rag_index = 0
    for k in keys:
        key_id = str(k["id"])
        qid = str(k.get("question_id") or "")
        expected = str(k.get("expected_answer") or "").strip()
        if not expected:
            continue
        max_marks = float(k.get("max_marks") or 0)
        sort_order = int(k.get("sort_order") or 0)
        stored_chunks = k.get("answer_chunks") or []

        if stored_chunks:
            for ch in stored_chunks:
                piece = str(ch.get("text_content") or "").strip()
                emb = ch.get("embedding") or []
                if not piece or not emb:
                    continue
                rows.append(
                    {
                        "chunk_id": f"key_{ch.get('chunk_id') or f'{key_id}_c{ch.get('chunk_index', 0)}'}",
                        "document_id": document_id,
                        "chunk_index": rag_index,
                        "text_content": f"Question {qid}.\nModel answer excerpt: {piece}",
                        "embedding": [float(x) for x in emb],
                        "meta": {
                            "kind": "answer_key",
                            "exam_id": exam_id,
                            "question_id": qid,
                            "key_id": key_id,
                            "max_marks": max_marks,
                            "answer_chunk_index": int(ch.get("chunk_index") or 0),
                            "char_start": ch.get("char_start"),
                            "char_end": ch.get("char_end"),
                        },
                    }
                )
                rag_index += 1
            continue

        text = f"Question {qid}.\nModel answer: {expected}"
        emb = k.get("embedding") or []
        if not emb:
            emb = embed_texts_batch([expected])[0]
        rows.append(
            {
                "chunk_id": f"key_{key_id}",
                "document_id": document_id,
                "chunk_index": rag_index,
                "text_content": text,
                "embedding": [float(x) for x in emb],
                "meta": {
                    "kind": "answer_key",
                    "exam_id": exam_id,
                    "question_id": qid,
                    "key_id": key_id,
                    "max_marks": max_marks,
                },
            }
        )
        rag_index += 1

    if not rows:
        return {"status": "skipped", "reason": "empty_keys", "exam_id": exam_id}

    n = upsert_rag_chunks_batch(rows)
    logger.info("ingest_keys_rag exam=%s document_id=%s chunks=%s", exam_id, document_id, n)
    return {
        "status": "success",
        "exam_id": exam_id,
        "document_id": document_id,
        "chunks_saved": n,
        "key_count": len(rows),
    }


def sync_exam_ingest(exam_id: str, *, sheet_id: Optional[str] = None) -> Dict[str, Any]:
    """Re-index keys for an exam and optionally re-ingest a linked answer sheet."""
    out: Dict[str, Any] = {"exam_id": exam_id, "keys": ingest_keys_rag(exam_id, force=True)}
    if sheet_id:
        row = get_sheet(sheet_id)
        if row and str(row.get("exam_id") or "") == exam_id:
            out["sheet"] = ingest_sheet_rag(sheet_id, force=True)
        else:
            out["sheet"] = {
                "status": "skipped",
                "reason": "sheet_exam_mismatch",
                "sheet_id": sheet_id,
            }
    return out


def _pdf_page_count(path: Path) -> int:
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError("PDF ingestion requires pymupdf (pip install pymupdf)") from e
    doc = fitz.open(str(path))
    try:
        return max(1, len(doc))
    finally:
        doc.close()


def _preprocess_options_from_env() -> Dict[str, Any]:
    opts: Dict[str, Any] = {}
    if os.environ.get("GRADE_OCR_FULL_PAGE", "").strip().lower() in {"1", "true", "yes", "on"}:
        opts["full_page"] = True
    return opts


def ingest_sheet_rag(
    sheet_id: str,
    *,
    force: bool = False,
    expected_num_regions: Optional[int] = None,
    regions_per_page: Optional[List[int]] = None,
    full_page: Optional[bool] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """
    OCR + chunk + embed an uploaded sheet and upsert into ``rag_chunks``.

    Returns status dict with ``chunks_saved``, ``document_id``, ``pages_processed``.
    """
    row = get_sheet(sheet_id)
    if not row:
        return {"status": "error", "reason": "sheet_not_found", "sheet_id": sheet_id}

    path = Path(str(row["path"]))
    if not path.is_file():
        return {"status": "error", "reason": "file_missing", "path": str(path)}

    document_id = sheet_document_id(sheet_id)
    exam_id = str(row.get("exam_id") or "")
    keys = list_answer_keys(exam_id) if exam_id else []

    if not force:
        existing = get_rag_chunks_for_sheet(sheet_id, limit=1)
        if existing:
            return {
                "status": "cached",
                "sheet_id": sheet_id,
                "document_id": document_id,
                "chunks_saved": len(get_rag_chunks_for_sheet(sheet_id, limit=2000)),
            }

    delete_rag_chunks_for_document(document_id)

    layout = resolve_regions_per_page(
        exam_id,
        regions_per_page=regions_per_page,
        num_keys=len(keys),
    )
    pp = preprocess_sheet_for_evaluation(
        path,
        exam_id=exam_id,
        num_answer_keys=len(keys),
        expected_num_regions=expected_num_regions,
        regions_per_page=layout,
        **_preprocess_options_from_env(),
    )
    preprocess_meta: Dict[str, Any] = {
        "pages": pp.diagnostics.get("pages") or [],
        "regions_per_page": layout,
        "key_region_groups": pp.diagnostics.get("key_region_groups"),
    }

    question_regions: List[Dict[str, Any]] = []
    for item in pp.diagnostics.get("question_regions") or []:
        qi = int(item.get("question_index") or 0)
        key = keys[min(qi, len(keys) - 1)] if keys else {}
        question_regions.append(
            {
                "question_id": str(key.get("question_id") or f"Q{qi + 1}"),
                "question_index": qi,
                "region_index": int(item.get("region_index") or qi),
                "raw_region_indices": item.get("raw_region_indices") or [],
                "region_ids": item.get("region_ids") or [],
                "page_start": int(item.get("page_start") or 1),
                "page_end": int(item.get("page_end") or 1),
                "pages": item.get("pages") or [],
                "segments": item.get("segments") or [],
            }
        )
    if question_regions:
        try:
            update_sheet_question_regions(sheet_id, question_regions)
        except Exception as e:
            logger.warning("Could not persist sheet question regions for %s: %s", sheet_id, e)

    all_regions: List[Dict[str, Any]] = []
    answer_rows: List[Dict[str, Any]] = []
    ocr_groups = pp.ocr_patch_groups or [[p] for p in pp.patches]
    total_patches = len(pp.patches)
    for i, patch in enumerate(pp.patches):
        parts = ocr_groups[i] if i < len(ocr_groups) else [patch]
        texts: List[str] = []
        confs: List[float] = []
        engines: List[str] = []
        flags: List[str] = []
        for part in parts:
            ocr_res = ocr_patch(part)
            engines.append(ocr_res.engine)
            if (ocr_res.text or "").strip():
                texts.append((ocr_res.text or "").strip())
            confs.append(float(ocr_res.confidence))
            flags.extend(ocr_res.flags or [])
        rid = pp.region_ids[i] if i < len(pp.region_ids) else f"R{i + 1}"
        all_regions.append(
            {
                "region_id": rid,
                "text": "\n\n".join(texts),
                "ocr_engine": ",".join(sorted(set(engines))),
                "ocr_confidence": sum(confs) / len(confs) if confs else 0.0,
                "flags": list(set(flags)),
            }
        )
        key = keys[i] if i < len(keys) else {}
        qr_item = next(
            (
                x
                for x in question_regions
                if int(x.get("question_index") or -1) == int(i)
                or str(x.get("question_id") or "") == str(key.get("question_id") or "")
            ),
            None,
        )
        answer_rows.append(
            {
                "question_id": str(key.get("question_id") or f"Q{i+1}"),
                "question_index": i,
                "region_index": i,
                "page_start": int((qr_item or {}).get("page_start") or 1),
                "page_end": int((qr_item or {}).get("page_end") or 1),
                "pages": (qr_item or {}).get("pages") or [],
                "segments": (qr_item or {}).get("segments") or [],
                "raw_ocr_text": "\n\n".join(texts),
                "formatted_answer_text": "",
                "format_flags": list(set(flags)),
                "boundary_confidence": 0.85 if qr_item else 0.5,
            }
        )
        if progress_callback:
            progress_callback(i + 1, total_patches)

    if not all_regions:
        return {"status": "skipped", "reason": "no_regions", "sheet_id": sheet_id}

    payload = build_rag_payload(
        source_path=str(path.resolve()),
        page=0,
        regions=all_regions,
        preprocess=preprocess_meta,
        document_id=document_id,
    )
    rows = rag_rows_for_postgres(payload)
    persisted_answers = list_sheet_question_answers(sheet_id)
    if answer_rows and (force or not persisted_answers):
        try:
            upsert_sheet_question_answers(sheet_id, exam_id, answer_rows)
            persisted_answers = list_sheet_question_answers(sheet_id)
        except Exception as e:
            logger.warning("Could not persist question answers for %s: %s", sheet_id, e)
    rid_to_qid: Dict[str, str] = {}
    qid_by_region: Dict[int, str] = {}
    for i in range(len(pp.patches)):
        rid = pp.region_ids[i] if i < len(pp.region_ids) else f"R{i + 1}"
        key = keys[i] if i < len(keys) else {}
        qid = str(key.get("question_id") or f"Q{i + 1}")
        rid_to_qid[str(rid)] = qid
        qid_by_region[i] = qid
    for a in persisted_answers:
        ri = int(a.get("region_index") or -1)
        qid = str(a.get("question_id") or "")
        if ri >= 0 and qid:
            qid_by_region[ri] = qid
    for r in rows:
        meta = dict(r.get("meta") or {})
        meta["kind"] = "sheet"
        meta["sheet_id"] = sheet_id
        meta["exam_id"] = exam_id
        meta["source_path"] = str(path.resolve())
        meta["document_id"] = document_id
        rid = str(meta.get("region_id") or "")
        qid = rid_to_qid.get(rid)
        if not qid and rid.startswith("R"):
            try:
                qid = qid_by_region.get(int(rid[1:]) - 1)
            except ValueError:
                qid = None
        if qid:
            meta["question_id"] = qid
        r["meta"] = meta

    n = upsert_rag_chunks_batch(rows)
    logger.info("ingest_sheet_rag sheet=%s document_id=%s chunks=%s", sheet_id, document_id, n)
    return {
        "status": "success",
        "sheet_id": sheet_id,
        "document_id": document_id,
        "chunks_saved": n,
        "pages_processed": int(pp.diagnostics.get("pdf_pages") or 1),
        "regions_ocr": len(all_regions),
    }
