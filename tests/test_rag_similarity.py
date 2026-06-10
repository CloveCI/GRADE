"""RAG similarity scoring: temperature, threshold, hybrid annotation."""

from __future__ import annotations

import os

import pytest

from autograder.rag.similarity import (
    annotate_hits_with_similarity,
    apply_similarity_temperature,
    chunk_query_similarity,
    filter_hits_by_threshold,
    similarity_from_distance,
)


def test_similarity_from_distance():
    assert similarity_from_distance(0.0) == pytest.approx(1.0)
    assert similarity_from_distance(0.2) == pytest.approx(0.8)
    assert similarity_from_distance(None) == 0.0


def test_temperature_rescales_scores():
    raw = 0.8
    strict = apply_similarity_temperature(raw, temperature=0.85)
    assert strict < raw
    lenient = apply_similarity_temperature(raw, temperature=1.2)
    assert lenient > raw


def test_filter_hits_by_threshold_drops_weak():
    hits = [
        {"chunk_id": "a", "similarity": 0.9, "score": 0.9},
        {"chunk_id": "b", "similarity": 0.2, "score": 0.2},
    ]
    out = filter_hits_by_threshold(hits, threshold=0.35, min_keep=1)
    assert len(out) == 1
    assert out[0]["chunk_id"] == "a"


def test_filter_keeps_best_when_all_below_threshold():
    hits = [
        {"chunk_id": "low", "similarity": 0.1, "score": 0.1},
        {"chunk_id": "high", "similarity": 0.2, "score": 0.2},
    ]
    out = filter_hits_by_threshold(hits, threshold=0.5, min_keep=1)
    assert len(out) == 1
    assert out[0]["chunk_id"] == "high"


def test_annotate_hits_adds_score_from_vector_distance(monkeypatch):
    monkeypatch.delenv("GRADE_RAG_SIM_TEMPERATURE", raising=False)
    q = [1.0] + [0.0] * 127
    hits = [{"chunk_id": "x", "vector_distance": 0.1, "text_content": "hello"}]
    out = annotate_hits_with_similarity(hits, q, temperature=1.0)
    assert out[0]["similarity"] == pytest.approx(0.9, abs=1e-6)
    assert out[0]["score"] == pytest.approx(0.9, abs=1e-6)


def test_chunk_query_similarity_uses_vector_distance():
    hit = {"vector_distance": 0.25, "text_content": "ignored for ANN path"}
    assert chunk_query_similarity([0.1] * 128, hit, reembed_text=False) == pytest.approx(0.75)
