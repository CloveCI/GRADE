"""
Ingest uploaded answer sheets into ``public.rag_chunks`` (GRADE 128-D + pgvector).

Adapted from repo ``tasks/ingestion_tasks.py`` + ``processing/embedder.py`` patterns:
chunk → embed → upsert, scoped per sheet via stable ``document_id``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from autograder.db import (
    delete_rag_chunks_for_document,
    get_rag_chunks_for_sheet,
    get_sheet,
    list_answer_keys,
    upsert_rag_chunks_batch,
)
from autograder.embeddings import embed_text_local
from autograder.ocr import ocr_patch
from autograder.preprocessing import preprocess_pipeline
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
    for k in keys:
        key_id = str(k["id"])
        qid = str(k.get("question_id") or "")
        expected = str(k.get("expected_answer") or "").strip()
        if not expected:
            continue
        emb = k.get("embedding") or []
        if not emb:
            emb = embed_text_local(expected)
        else:
            emb = [float(x) for x in emb]
        text = f"Question {qid}.\nModel answer: {expected}"
        rows.append(
            {
                "chunk_id": f"key_{key_id}",
                "document_id": document_id,
                "chunk_index": int(k.get("sort_order") or 0),
                "text_content": text,
                "embedding": emb,
                "meta": {
                    "kind": "answer_key",
                    "exam_id": exam_id,
                    "question_id": qid,
                    "key_id": key_id,
                    "max_marks": float(k.get("max_marks") or 0),
                },
            }
        )

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
    full_page: Optional[bool] = None,
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
    exam_id = row.get("exam_id")

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

    use_full_page = full_page
    if use_full_page is None:
        use_full_page = _preprocess_options_from_env().get("full_page", True)

    is_pdf = path.suffix.lower() == ".pdf"
    page_count = _pdf_page_count(path) if is_pdf else 1

    all_regions: List[Dict[str, Any]] = []
    preprocess_meta: Dict[str, Any] = {"pages": []}

    for page_idx in range(page_count):
        pp = preprocess_pipeline(
            path,
            expected_num_regions=expected_num_regions,
            pdf_page_index=page_idx,
            full_page=bool(use_full_page),
        )
        preprocess_meta["pages"].append(
            {
                "page": page_idx + 1,
                "regions_found": len(pp.patches),
                "fallback_grid": pp.used_fallback_grid,
                "diagnostics": pp.diagnostics,
            }
        )
        for i, patch in enumerate(pp.patches):
            ocr_res = ocr_patch(patch)
            rid = pp.region_ids[i] if i < len(pp.region_ids) else f"R{i + 1}"
            if page_count > 1:
                rid = f"P{page_idx + 1}_{rid}"
            all_regions.append(
                {
                    "region_id": rid,
                    "text": ocr_res.text,
                    "ocr_engine": ocr_res.engine,
                    "ocr_confidence": ocr_res.confidence,
                    "flags": list(ocr_res.flags or []),
                }
            )

    if not all_regions:
        return {"status": "skipped", "reason": "no_regions", "sheet_id": sheet_id}

    payload = build_rag_payload(
        source_path=str(path.resolve()),
        page=0,
        regions=all_regions,
        preprocess=preprocess_meta,
        document_id=document_id,
    )
    rows = rag_rows_for_postgres(payload, embed_fn=embed_text_local)
    for r in rows:
        meta = dict(r.get("meta") or {})
        meta["kind"] = "sheet"
        meta["sheet_id"] = sheet_id
        meta["exam_id"] = exam_id
        meta["source_path"] = str(path.resolve())
        meta["document_id"] = document_id
        r["meta"] = meta

    n = upsert_rag_chunks_batch(rows)
    logger.info("ingest_sheet_rag sheet=%s document_id=%s chunks=%s", sheet_id, document_id, n)
    return {
        "status": "success",
        "sheet_id": sheet_id,
        "document_id": document_id,
        "chunks_saved": n,
        "pages_processed": page_count,
        "regions_ocr": len(all_regions),
    }
