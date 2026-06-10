"""Hybrid retrieval and answer-key matching for GRADE evaluate + RAG explorer."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from autograder.db import get_sheet, hybrid_search_rag_chunks, list_answer_keys
from autograder.embeddings import embed_text_local, retrieve_top_k
from autograder.rag.ingest import exam_rag_document_ids, keys_document_id, sheet_document_id
from autograder.rag.query import process_query
from autograder.rag.similarity import filter_hits_by_threshold

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

    qids = [str(k.get("question_id") or "") for k in keys]
    if len(qids) != len(set(qids)):
        return keys[min(region_index, len(keys) - 1)]

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


def _key_corpus_query(key: Dict[str, Any]) -> str:
    qid = str(key.get("question_id") or "")
    expected = str(key.get("expected_answer") or "").strip()
    return process_query(f"Question {qid} model answer reference {expected}")


def _sheet_corpus_query(student_text: str, key: Dict[str, Any]) -> str:
    qid = str(key.get("question_id") or "")
    return process_query(f"Question {qid} student handwritten answer {student_text}")


def _region_token(region_index: Optional[int]) -> Optional[str]:
    if region_index is None:
        return None
    return f"R{region_index + 1}"


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
    return f"sheet {region}".strip() if region else "sheet"


def _sort_sheet_hits_for_region(
    hits: List[Dict[str, Any]],
    region_index: Optional[int],
) -> List[Dict[str, Any]]:
    """Prefer chunks from the OCR patch being graded (region_id R1, R2, …)."""
    if region_index is None or not hits:
        return hits
    token = _region_token(region_index)
    if not token:
        return hits

    def _rank(h: Dict[str, Any]) -> Tuple[int, float]:
        meta = h.get("meta") or {}
        rid = str(meta.get("region_id") or "")
        region_match = 0 if (rid == token or token in rid) else 1
        score = h.get("score")
        if score is None:
            score = h.get("similarity")
        if score is None:
            dist = h.get("vector_distance", h.get("distance"))
            score = 1.0 - float(dist or 1.0)
        return (region_match, -float(score))

    return sorted(hits, key=_rank)


def _hits_for_question(
    hits: List[Dict[str, Any]],
    question_id: str,
    *,
    corpus: str,
) -> List[Dict[str, Any]]:
    """Prefer chunks tagged with the same question_id (answer-key corpus)."""
    if not question_id:
        return hits
    q = question_id.strip().lower()
    matched: List[Dict[str, Any]] = []
    rest: List[Dict[str, Any]] = []
    for h in hits:
        meta = h.get("meta") or {}
        kind = str(meta.get("kind") or "")
        if corpus == "answer_key" and kind != "answer_key":
            doc = str(h.get("document_id") or "")
            if not doc.startswith("keys_"):
                rest.append(h)
                continue
        hq = str(meta.get("question_id") or "").strip().lower()
        if hq == q:
            matched.append(h)
        else:
            rest.append(h)
    return matched + rest


def _append_excerpts(
    parts: List[str],
    chunk_ids: List[str],
    hits: List[Dict[str, Any]],
    *,
    max_chars: int,
    used: int,
    skip_chunk_id: Optional[str] = None,
) -> int:
    for h in hits:
        cid = str(h.get("chunk_id") or "")
        if skip_chunk_id and cid == skip_chunk_id:
            continue
        text = (h.get("text_content") or "").strip()
        if not text:
            continue
        label = _hit_label(h)
        block = f"- [{label}] {text}"
        if used + len(block) + 2 > max_chars:
            break
        parts.append(block)
        if cid:
            chunk_ids.append(cid)
        used += len(block) + 2
    return used


def format_grading_context(
    *,
    question_id: str,
    model_answer: str,
    student_ocr: str,
    key_hits: List[Dict[str, Any]],
    sheet_hits: List[Dict[str, Any]],
    region_index: Optional[int] = None,
    max_chars: int = 3200,
) -> Dict[str, Any]:
    """
    Build a side-by-side, anti-hallucination prompt block for the grading LLM.

    KEY SIDE = official answer + retrieved key RAG chunks.
    STUDENT SIDE = OCR + retrieved sheet RAG chunks for the same exam.
    """
    qid = question_id or "?"
    region_note = ""
    if region_index is not None:
        region_note = f" (OCR region {_region_token(region_index)})"

    key_lines: List[str] = [
        f"=== KEY SIDE — Question {qid} ===",
        f"Official model answer: {model_answer.strip() or '(not provided)'}",
        "Retrieved excerpts from answer-key index (pgvector):",
    ]
    sheet_lines: List[str] = [
        f"=== STUDENT SIDE — Question {qid}{region_note} ===",
        f"OCR text: {student_ocr.strip() or '(empty)'}",
        "Retrieved excerpts from this student's sheet index (pgvector):",
    ]
    chunk_ids: List[str] = []
    used = sum(len(x) + 1 for x in key_lines + sheet_lines)

    used = _append_excerpts(key_lines, chunk_ids, key_hits, max_chars=max_chars, used=used)
    used = _append_excerpts(sheet_lines, chunk_ids, sheet_hits, max_chars=max_chars, used=used)

    if len(key_lines) <= 3:
        key_lines.append("- (no additional key chunks retrieved)")
    if len(sheet_lines) <= 3:
        sheet_lines.append("- (no additional sheet chunks retrieved)")

    context_text = "\n".join(
        key_lines
        + [""]
        + sheet_lines
        + [
            "",
            "=== INSTRUCTIONS ===",
            "Compare STUDENT SIDE to KEY SIDE for semantic equivalence on this question only.",
            "Use only the text above; do not add outside knowledge.",
        ]
    )

    return {
        "context_text": context_text[: max_chars + 400],
        "chunk_ids": chunk_ids,
        "key_hit_count": len(key_hits),
        "sheet_hit_count": len(sheet_hits),
        "question_id": qid,
        "region_index": region_index,
    }


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


def hybrid_search_for_keys(exam_id: str, query: str, *, top_k: int = 5) -> List[Dict[str, Any]]:
    """Search only the answer-key RAG corpus for an exam."""
    q = process_query(query)
    if not q:
        return []
    qv = embed_text_local(q)
    return hybrid_search_rag_chunks(q, qv, top_k=top_k, document_id=keys_document_id(exam_id))


def retrieve_context_for_grading(
    sheet_id: str,
    exam_id: str,
    student_text: str,
    key: Dict[str, Any],
    *,
    top_k: int = 3,
    region_index: Optional[int] = None,
    max_chars: int = 3200,
) -> Dict[str, Any]:
    """
    Build grounded LLM context: dual-corpus hybrid RAG (keys + sheet) formatted side-by-side.

    1. Search ``keys_{exam_id}`` for model-answer chunks for this question.
    2. Search ``sheet_{sheet_id}`` for student handwriting chunks (region-aware when possible).
    3. Format KEY SIDE vs STUDENT SIDE so the LLM compares without inventing content.
    """
    qid = str(key.get("question_id") or "")
    expected = str(key.get("expected_answer") or "").strip()
    per_corpus = max(top_k, 4)

    key_hits = hybrid_search_for_keys(exam_id, _key_corpus_query(key), top_k=per_corpus)
    key_hits = _hits_for_question(key_hits, qid, corpus="answer_key")
    key_hits = filter_hits_by_threshold(key_hits, min_keep=1)

    sheet_query = _sheet_corpus_query(student_text, key)
    sheet_hits = hybrid_search_rag_chunks(
        sheet_query,
        embed_text_local(sheet_query),
        top_k=per_corpus,
        document_id=sheet_document_id(sheet_id),
    )
    sheet_hits = _sort_sheet_hits_for_region(sheet_hits, region_index)
    sheet_hits = filter_hits_by_threshold(sheet_hits, min_keep=1)

    # Combined hits for API/UI (explorer, debugging)
    all_hits = key_hits + sheet_hits

    formatted = format_grading_context(
        question_id=qid,
        model_answer=expected,
        student_ocr=student_text,
        key_hits=key_hits,
        sheet_hits=sheet_hits,
        region_index=region_index,
        max_chars=max_chars,
    )

    kid = str(key.get("id") or "")
    if kid and f"key_{kid}" not in formatted["chunk_ids"]:
        formatted["chunk_ids"].insert(0, f"key_{kid}")

    return {
        "context_text": formatted["context_text"],
        "chunk_ids": formatted["chunk_ids"],
        "hits": all_hits,
        "key_hits": key_hits,
        "sheet_hits": sheet_hits,
        "exam_id": exam_id,
        "document_ids": exam_rag_document_ids(exam_id, sheet_id),
        "question_id": qid,
        "region_index": region_index,
        "key_hit_count": formatted["key_hit_count"],
        "sheet_hit_count": formatted["sheet_hit_count"],
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
