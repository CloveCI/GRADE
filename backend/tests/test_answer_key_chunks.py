"""Answer key chunk build + retrieve_top_k over answer_chunks."""

import os

import pytest

os.environ.setdefault("GRADE_EMBED_BACKEND", "hash")

from autograder.embeddings import EMBEDDING_DIMS, embed_text, retrieve_top_k
from autograder.key_chunks import aggregate_key_embedding, build_answer_key_chunks


@pytest.fixture(autouse=True)
def _hash_backend(monkeypatch):
    monkeypatch.setenv("GRADE_EMBED_BACKEND", "hash")


def test_build_answer_key_chunks_multiple():
    text = "word " * 120
    rows = build_answer_key_chunks(text, key_id="kid1")
    assert len(rows) >= 2
    assert all(len(r["embedding"]) == EMBEDDING_DIMS for r in rows)
    assert rows[0]["chunk_id"] == "kid1_c0"


def test_aggregate_key_embedding_unit_norm():
    rows = build_answer_key_chunks("short answer", key_id="k2")
    agg = aggregate_key_embedding(rows)
    assert len(agg) == EMBEDDING_DIMS
    norm = sum(v * v for v in agg) ** 0.5
    assert 0.99 <= norm <= 1.01


def test_retrieve_top_k_uses_best_chunk():
    full = "photosynthesis chlorophyll sunlight glucose"
    short = "quantum mechanics particle wave"
    chunks_full = build_answer_key_chunks(full, key_id="a")
    chunks_short = build_answer_key_chunks(short, key_id="b")
    keys = [
        {
            "question_id": "Q1",
            "expected_answer": full,
            "answer_chunks": chunks_full,
            "embedding": aggregate_key_embedding(chunks_full),
        },
        {
            "question_id": "Q2",
            "expected_answer": short,
            "answer_chunks": chunks_short,
            "embedding": aggregate_key_embedding(chunks_short),
        },
    ]
    top = retrieve_top_k("chlorophyll plant biology", keys, top_k=1)
    assert top[0][0]["question_id"] == "Q1"
