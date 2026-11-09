"""RAG retrieval similarity: cosine scores, temperature scaling, and thresholds."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

from autograder.embeddings import cosine_similarity, embed_text_local


def rag_similarity_threshold() -> float:
    """Drop chunks below this raw cosine similarity (``GRADE_RAG_SIM_THRESHOLD``)."""
    raw = os.environ.get("GRADE_RAG_SIM_THRESHOLD", "0.35").strip()
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.35


def rag_similarity_temperature() -> float:
    """
    Rescale displayed/ranking scores (``GRADE_RAG_SIM_TEMPERATURE``).

    Applied as ``similarity ** (1/T)``:

    * ``T < 1`` — suppress weak matches (stricter displayed scores).
    * ``T = 1`` — raw cosine similarity.
    * ``T > 1`` — boost strong matches (lenient displayed scores).
    """
    raw = os.environ.get("GRADE_RAG_SIM_TEMPERATURE", "0.85").strip()
    try:
        t = float(raw)
        return t if t > 0 else 1.0
    except ValueError:
        return 0.85


def similarity_from_distance(distance: Optional[float]) -> float:
    """pgvector cosine distance ``<=>`` → similarity in [0, 1]."""
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


def apply_similarity_temperature(similarity: float, temperature: Optional[float] = None) -> float:
    """Power-map cosine similarity; ``T=0.85`` makes 0.8 → ~0.77, 0.4 → ~0.33."""
    sim = max(0.0, min(1.0, float(similarity)))
    temp = rag_similarity_temperature() if temperature is None else temperature
    if temp <= 0 or abs(temp - 1.0) < 1e-9:
        return sim
    return sim ** (1.0 / temp)


def chunk_query_similarity(
    query_embedding: Sequence[float],
    hit: Dict[str, Any],
    *,
    reembed_text: bool = True,
) -> float:
    """
    Cosine similarity between query vector and a ``rag_chunks`` hit.

    Uses ``vector_distance`` from ANN when present; otherwise re-embeds ``text_content``.
    """
    if hit.get("vector_distance") is not None:
        return similarity_from_distance(hit.get("vector_distance"))
    dist = hit.get("distance")
    meta = hit.get("meta") or {}
    if meta.get("bm25_score") is not None and hit.get("vector_distance") is None:
        pass
    elif dist is not None and hit.get("fused_score") is None:
        return similarity_from_distance(dist)

    if not reembed_text:
        return 0.0
    text = (hit.get("text_content") or "").strip()
    if not text or not query_embedding:
        return 0.0
    chunk_emb = embed_text_local(text)
    return max(0.0, cosine_similarity(query_embedding, chunk_emb))


def annotate_hits_with_similarity(
    hits: List[Dict[str, Any]],
    query_embedding: Sequence[float],
    *,
    temperature: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Add ``similarity`` (raw cosine) and ``score`` (temperature-scaled) to each hit."""
    temp = rag_similarity_temperature() if temperature is None else temperature
    out: List[Dict[str, Any]] = []
    for h in hits:
        row = dict(h)
        raw = chunk_query_similarity(query_embedding, row)
        row["similarity"] = raw
        row["score"] = apply_similarity_temperature(raw, temp)
        if row.get("vector_distance") is None and raw > 0:
            row["vector_distance"] = 1.0 - raw
        out.append(row)
    out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return out


def filter_hits_by_threshold(
    hits: List[Dict[str, Any]],
    *,
    threshold: Optional[float] = None,
    min_keep: int = 1,
) -> List[Dict[str, Any]]:
    """
    Keep hits at or above ``threshold``, plus any hit that matched full-text search (``fts_match``); retain at least
    ``min_keep`` best if all fail. Noisy handwriting OCR lowers cosine similarity (a correct chunk scored 0.32 vs the
    0.35 default), so an exact keyword match is allowed to survive the cut-off.
    """
    if not hits:
        return []
    thr = rag_similarity_threshold() if threshold is None else threshold
    passed = [h for h in hits if h.get("fts_match") or float(h.get("similarity") or 0.0) >= thr]
    if passed:
        return passed
    if min_keep <= 0:
        return []
    ranked = sorted(hits, key=lambda x: float(x.get("similarity") or 0.0), reverse=True)
    return ranked[: min_keep]
