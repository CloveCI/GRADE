"""Hybrid retrieval and answer-key matching for GRADE evaluate + RAG explorer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from autograder.db import get_sheet, hybrid_search_rag_chunks, list_answer_keys
from autograder.embeddings import embed_text_local, retrieve_top_k
from autograder.rag.ingest import exam_rag_document_ids, keys_document_id, sheet_document_id
from autograder.rag.query import process_query

_EMBED_MATCH_MIN = 0.28


def match_answer_key(
    region_index: int,
    student_text: str,
    keys: List[Dict[str, Any]],
    *,
    top_k: int = 3,
) -> Dict[str, Any]:
    """
    Map an OCR region to the best answer-key row.

    Uses embedding similarity when regions exceed key count or similarity is strong;
    otherwise keeps positional alignment for typical 1:1 layouts.
    """
    if not keys:
        raise ValueError("keys cannot be empty")

    top = retrieve_top_k(student_text, keys, top_k=top_k)
    if top:
        emb_key, sim = top[0]
        if region_index >= len(keys) or sim >= _EMBED_MATCH_MIN:
            return emb_key

    if region_index < len(keys):
        return keys[region_index]
    return keys[-1]


def _grading_query(student_text: str, key: Dict[str, Any]) -> str:
    qid = str(key.get("question_id") or "")
    expected = str(key.get("expected_answer") or "")
    return process_query(f"{qid} {expected} {student_text}")


def _hit_label(hit: Dict[str, Any]) -> str:
    meta = hit.get("meta") or {}
    kind = str(meta.get("kind") or "")
    if not kind:
        doc = str(hit.get("document_id") or "")
        kind = "answer_key" if doc.startswith("keys_") else "sheet"
    qid = meta.get("question_id") or ""
    if kind == "answer_key":
        return f"answer_key {qid}".strip()
    page = meta.get("source_page")
    region = meta.get("region_id") or ""
    if page is not None:
        return f"sheet p{page} {region}".strip()
    return "sheet"


def hybrid_search_for_sheet(
    sheet_id: str,
    query: str,
    *,
    top_k: int = 5,
    exam_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Hybrid search on sheet chunks, or sheet + keys when ``exam_id`` is set."""
    sheet = get_sheet(sheet_id)
    if not sheet:
        return []
    ex = exam_id or str(sheet.get("exam_id") or "").strip() or None
    if ex:
        return hybrid_search_for_exam(sheet_id, ex, query, top_k=top_k)

    q = process_query(query)
    if not q:
        return []
    doc_id = sheet_document_id(sheet_id)
    qv = embed_text_local(q)
    return hybrid_search_rag_chunks(q, qv, top_k=top_k, document_id=doc_id)


def hybrid_search_for_exam(
    sheet_id: str,
    exam_id: str,
    query: str,
    *,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Retrieve from both ``keys_{exam_id}`` and ``sheet_{sheet_id}`` corpora."""
    q = process_query(query)
    if not q:
        return []
    doc_ids = exam_rag_document_ids(exam_id, sheet_id)
    qv = embed_text_local(q)
    return hybrid_search_rag_chunks(q, qv, top_k=top_k, document_ids=doc_ids)


def retrieve_context_for_grading(
    sheet_id: str,
    exam_id: str,
    student_text: str,
    key: Dict[str, Any],
    *,
    top_k: int = 3,
    max_chars: int = 2400,
) -> Dict[str, Any]:
    """
    Build LLM context from the matched key plus hybrid RAG over sheet + key chunks.
    """
    qid = str(key.get("question_id") or "")
    expected = str(key.get("expected_answer") or "").strip()
    parts: List[str] = []
    chunk_ids: List[str] = []
    used = 0

    if expected:
        key_block = f"[answer_key {qid}] Model answer: {expected}"
        parts.append(key_block)
        used += len(key_block) + 1
        kid = str(key.get("id") or "")
        if kid:
            chunk_ids.append(f"key_{kid}")

    hits = hybrid_search_for_exam(
        sheet_id,
        exam_id,
        _grading_query(student_text, key),
        top_k=max(top_k, 5),
    )

    matched_key_chunk = f"key_{key.get('id')}" if key.get("id") else None
    for h in hits:
        cid = str(h.get("chunk_id") or "")
        if matched_key_chunk and cid == matched_key_chunk and len(parts) > 1:
            continue
        text = (h.get("text_content") or "").strip()
        if not text:
            continue
        label = _hit_label(h)
        block = f"[{label}] {text}"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        if cid:
            chunk_ids.append(cid)
        used += len(block) + 1

    return {
        "context_text": "\n\n".join(parts),
        "chunk_ids": chunk_ids,
        "hits": hits,
        "exam_id": exam_id,
        "document_ids": exam_rag_document_ids(exam_id, sheet_id),
    }


def retrieve_key_neighbors(
    exam_id: str,
    student_text: str,
    *,
    top_k: int = 3,
) -> List[Tuple[Dict[str, Any], float]]:
    """Top answer-key rows by embedding similarity (for debugging / RAG explorer)."""
    keys = list_answer_keys(exam_id)
    return retrieve_top_k(student_text, keys, top_k=top_k)


def hybrid_search_for_keys(exam_id: str, query: str, *, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search only the answer-key RAG corpus for an exam."""
    q = process_query(query)
    if not q:
        return []
    qv = embed_text_local(q)
    return hybrid_search_rag_chunks(q, qv, top_k=top_k, document_id=keys_document_id(exam_id))
