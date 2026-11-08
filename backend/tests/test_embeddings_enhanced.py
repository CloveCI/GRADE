"""Embedding + chunk helpers (hash backend for CI; no model download required)."""

import os

import pytest

# Force deterministic hash path before autograder.embeddings resolves backend
os.environ.setdefault("GRADE_EMBED_BACKEND", "hash")

from autograder.embeddings import (  # noqa: E402
    EMBEDDING_DIMS,
    embed_text,
    embed_text_hash,
    embed_texts_batch,
    embedding_backend,
    max_embed_text_length,
    truncate_for_embedding,
)
from autograder.rag_extract import chunk_text, default_chunk_size, rag_rows_for_postgres


@pytest.fixture(autouse=True)
def _hash_backend(monkeypatch):
    monkeypatch.setenv("GRADE_EMBED_BACKEND", "hash")


def test_truncate_for_embedding():
    long = "x" * 5000
    out = truncate_for_embedding(long, max_len=2000)
    assert len(out) == 2000


def test_batch_embeddings_same_as_single():
    texts = ["alpha beta", "gamma delta"]
    batch = embed_texts_batch(texts)
    assert len(batch) == 2
    assert batch[0] == embed_text(texts[0])
    assert len(batch[0]) == EMBEDDING_DIMS


def test_chunk_respects_max_embed_length():
    t = "word " * 300
    chunks = chunk_text(t, chunk_size=200, overlap=40)
    cap = max_embed_text_length()
    assert all(len(c[0]) <= cap for c in chunks)


def test_rag_rows_batch_embed():
    payload = {
        "schema_version": "1.1",
        "document_id": "doc1",
        "chunks": [
            {"chunk_id": "a", "index": 0, "text": "one two", "metadata": {}},
            {"chunk_id": "b", "index": 1, "text": "three four", "metadata": {}},
        ],
    }
    rows = rag_rows_for_postgres(payload, batch_embed=True)
    assert len(rows) == 2
    assert all(len(r["embedding"]) == EMBEDDING_DIMS for r in rows)


def test_embedding_backend_hash_in_tests():
    assert embedding_backend() == "hash"


def test_default_chunk_size_within_cap():
    assert default_chunk_size() <= max_embed_text_length()


def test_empty_batch_returns_zeros():
    assert embed_texts_batch([]) == []
    assert embed_text_hash("") == [0.0] * EMBEDDING_DIMS
