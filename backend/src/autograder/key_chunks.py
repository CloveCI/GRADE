"""
Chunk + embed model answers for storage in ``answer_key_chunks`` (per-key RAG granularity).
"""

from __future__ import annotations

from typing import Any, Dict, List

from autograder.embeddings import embed_text, embed_texts_batch
from autograder.rag_extract import chunk_text, normalize_ocr_text


def build_answer_key_chunks(
    expected_answer: str,
    *,
    key_id: str,
) -> List[Dict[str, Any]]:
    """
    Split a model answer into chunked rows ready for ``upsert_answer_key_chunks``.

    Each row: ``chunk_id``, ``chunk_index``, ``text_content``, ``embedding``,
    optional ``char_start`` / ``char_end``.
    """
    normalized = normalize_ocr_text(expected_answer)
    if not normalized:
        return []

    pieces = chunk_text(normalized)
    if not pieces:
        return []

    texts = [p[0] for p in pieces]
    vectors = embed_texts_batch(texts) if len(texts) > 1 else [embed_text(texts[0])]

    rows: List[Dict[str, Any]] = []
    for i, ((piece, c0, c1), vec) in enumerate(zip(pieces, vectors)):
        rows.append(
            {
                "chunk_id": f"{key_id}_c{i}",
                "chunk_index": i,
                "text_content": piece,
                "embedding": vec,
                "char_start": c0,
                "char_end": c1,
            }
        )
    return rows


def aggregate_key_embedding(chunks: List[Dict[str, Any]]) -> List[float]:
    """Document-level vector for ``answer_keys.embedding`` (mean of chunk vectors)."""
    if not chunks:
        return []
    dim = len(chunks[0].get("embedding") or [])
    if dim == 0:
        return []
    acc = [0.0] * dim
    for ch in chunks:
        emb = ch.get("embedding") or []
        if len(emb) != dim:
            continue
        for i, v in enumerate(emb):
            acc[i] += float(v)
    n = float(len(chunks))
    mean = [v / n for v in acc]
    norm = sum(v * v for v in mean) ** 0.5
    if norm == 0:
        return mean
    return [v / norm for v in mean]
