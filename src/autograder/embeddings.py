"""
Text embeddings for GRADE (answer keys, RAG chunks, hybrid search).

Primary path follows ``processing/embedder.py`` (all-MiniLM-L6-v2, 384-D, batch encode,
MAX_TEXT_LENGTH=2000). Vectors are projected to ``EMBEDDING_DIMS`` (128) for pgvector storage.

Set ``GRADE_EMBED_BACKEND=hash`` to force the legacy deterministic hash embedder (tests/CI).
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import threading
from typing import Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# pgvector column width (see supabase migrations)
EMBEDDING_DIMS = 128

# processing/embedder.py defaults
MINILM_DIMS = 384
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
MAX_TEXT_LENGTH = 2000
DEFAULT_BATCH_SIZE = 32

_HASH_BACKEND = "hash"
_MINILM_BACKEND = "minilm"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_backend() -> str:
    raw = os.environ.get("GRADE_EMBED_BACKEND", "").strip().lower()
    if raw in {_HASH_BACKEND, _MINILM_BACKEND, "sentence-transformers", "st"}:
        return _MINILM_BACKEND if raw != _HASH_BACKEND else _HASH_BACKEND
    return _MINILM_BACKEND


def max_embed_text_length() -> int:
    return max(256, _env_int("GRADE_EMBED_MAX_LENGTH", MAX_TEXT_LENGTH))


def truncate_for_embedding(text: str, *, max_len: Optional[int] = None) -> str:
    """Truncate text before embedding (matches UnifiedEmbedder)."""
    limit = max_len if max_len is not None else max_embed_text_length()
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit]


def _zero_vector(dims: int = EMBEDDING_DIMS) -> List[float]:
    return [0.0] * dims


def embed_text_hash(text: str, dims: int = EMBEDDING_DIMS) -> List[float]:
    """Deterministic local embedding fallback using hashed token bins."""
    vec = [0.0] * dims
    tokens = [t for t in text.lower().split() if t]
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dims
        sign = -1.0 if (h >> 8) & 1 else 1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


_proj_matrix: Optional["object"] = None


def _projection_matrix() -> "object":
    global _proj_matrix
    if _proj_matrix is not None:
        return _proj_matrix
    import numpy as np

    rng = np.random.default_rng(42)
    proj = rng.standard_normal((EMBEDDING_DIMS, MINILM_DIMS)).astype(np.float32)
    norms = np.linalg.norm(proj, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    _proj_matrix = proj / norms
    return _proj_matrix


def _project_minilm(vec384: Sequence[float]) -> List[float]:
    import numpy as np

    v = np.asarray(vec384, dtype=np.float32).reshape(-1)
    if v.size != MINILM_DIMS:
        if v.size > MINILM_DIMS:
            v = v[:MINILM_DIMS]
        else:
            padded = np.zeros(MINILM_DIMS, dtype=np.float32)
            padded[: v.size] = v
            v = padded
    out = _projection_matrix() @ v
    norm = float(np.linalg.norm(out))
    if norm == 0:
        return _zero_vector()
    return (out / norm).tolist()


class GradeEmbedder:
    """
    Singleton sentence-transformer embedder (adapted from ``processing/embedder.UnifiedEmbedder``).
    """

    _instance: Optional["GradeEmbedder"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "GradeEmbedder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._initialized = False
                    cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self.model_name = os.environ.get("GRADE_EMBED_MODEL", "").strip() or DEFAULT_MODEL_NAME
        self.model = None
        self._load_error: Optional[str] = None
        try:
            self._load_model()
        except Exception as e:
            self._load_error = str(e)
            logger.warning("Sentence-transformer model not loaded: %s", e)
        self._initialized = True

    def _load_model(self) -> None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", self.model_name)
        self.model = SentenceTransformer(self.model_name)
        logger.info("Embedding model loaded")

    @property
    def available(self) -> bool:
        return self.model is not None

    def generate_embedding(self, text: str, *, normalize: bool = True) -> List[float]:
        t = truncate_for_embedding(text)
        if not t:
            return _zero_vector()
        if not self.available:
            raise RuntimeError(self._load_error or "embedding model not loaded")
        emb = self.model.encode(t, normalize_embeddings=normalize)
        return _project_minilm(emb)

    def batch_generate_embeddings(
        self,
        texts: List[str],
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        filter_empty: bool = True,
        normalize: bool = True,
    ) -> List[List[float]]:
        if not texts:
            return []
        if not self.available:
            raise RuntimeError(self._load_error or "embedding model not loaded")

        batch_size = max(1, _env_int("GRADE_EMBED_BATCH_SIZE", batch_size))
        limit = max_embed_text_length()

        if filter_empty:
            valid_texts: List[str] = []
            valid_indices: List[int] = []
            valid_set: set[int] = set()
            for i, text in enumerate(texts):
                t = truncate_for_embedding(text, max_len=limit)
                if t:
                    valid_texts.append(t)
                    valid_indices.append(i)
                    valid_set.add(i)
            if not valid_texts:
                return [_zero_vector() for _ in texts]
            embeddings = self.model.encode(
                valid_texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=False,
            )
            result: List[List[float]] = []
            vi = 0
            for i in range(len(texts)):
                if i in valid_set:
                    result.append(_project_minilm(embeddings[vi]))
                    vi += 1
                else:
                    result.append(_zero_vector())
            return result

        truncated = [truncate_for_embedding(t, max_len=limit) for t in texts]
        embeddings = self.model.encode(
            truncated,
            batch_size=batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
        return [_project_minilm(e) for e in embeddings]


_embedder: Optional[GradeEmbedder] = None
_embedder_lock = threading.Lock()
_backend_resolved: Optional[str] = None


def _active_backend() -> str:
    global _backend_resolved
    if _backend_resolved is not None:
        return _backend_resolved
    want = _env_backend()
    if want == _HASH_BACKEND:
        _backend_resolved = _HASH_BACKEND
        return _backend_resolved
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        logger.info("sentence-transformers not installed; using hash embeddings")
        _backend_resolved = _HASH_BACKEND
        return _backend_resolved
    _backend_resolved = _MINILM_BACKEND
    return _backend_resolved


def get_embedder() -> GradeEmbedder:
    """Singleton embedder (loads model on first use)."""
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                _embedder = GradeEmbedder()
    return _embedder


def embedding_backend() -> str:
    """``minilm`` or ``hash`` — which backend ``embed_text`` uses."""
    if _active_backend() == _HASH_BACKEND:
        return _HASH_BACKEND
    if get_embedder().available:
        return _MINILM_BACKEND
    return _HASH_BACKEND


def embed_text(text: str) -> List[float]:
    """Primary embedding API (MiniLM projected to 128-D, or hash fallback)."""
    t = truncate_for_embedding(text)
    if not t:
        return _zero_vector()
    if _active_backend() == _HASH_BACKEND or not get_embedder().available:
        return embed_text_hash(t)
    try:
        return get_embedder().generate_embedding(t)
    except Exception as e:
        logger.warning("MiniLM embed failed, using hash fallback: %s", e)
        return embed_text_hash(t)


def embed_texts_batch(texts: List[str]) -> List[List[float]]:
    """Batch embed (MiniLM batch path or per-item hash)."""
    if not texts:
        return []
    if _active_backend() == _HASH_BACKEND or not get_embedder().available:
        return [embed_text_hash(truncate_for_embedding(t)) for t in texts]
    try:
        return get_embedder().batch_generate_embeddings(texts)
    except Exception as e:
        logger.warning("MiniLM batch failed, using hash fallback: %s", e)
        return [embed_text_hash(truncate_for_embedding(t)) for t in texts]


def embed_text_local(text: str, dims: int = EMBEDDING_DIMS) -> List[float]:
    """Backward-compatible name used across GRADE; delegates to :func:`embed_text`."""
    v = embed_text(text)
    if len(v) == dims:
        return v
    if len(v) > dims:
        return v[:dims]
    return v + [0.0] * (dims - len(v))


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n)))
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n)))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def retrieve_top_k(
    student_text: str,
    candidates: Iterable[dict],
    top_k: int = 3,
) -> List[Tuple[dict, float]]:
    student_emb = embed_text(student_text)
    scored: List[Tuple[dict, float]] = []
    for c in candidates:
        chunks = c.get("answer_chunks") or []
        if chunks:
            sims = []
            for ch in chunks:
                emb = ch.get("embedding") or []
                if emb:
                    sims.append(cosine_similarity(student_emb, emb))
            sim = max(sims) if sims else 0.0
        else:
            emb = c.get("embedding") or []
            if emb and len(emb) != len(student_emb):
                emb = embed_text(str(c.get("expected_answer") or c.get("text_content") or ""))
            sim = cosine_similarity(student_emb, emb)
        scored.append((c, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
