"""Grounded grading context: dual-corpus KEY SIDE / STUDENT SIDE formatting."""

from __future__ import annotations

from autograder.rag.retrieval import format_grading_context, match_answer_key, retrieve_context_for_grading


def test_match_answer_key_uses_position_when_duplicate_question_ids():
    keys = [
        {"question_id": "Q1", "expected_answer": "alpha", "embedding": [1.0] + [0.0] * 127},
        {"question_id": "Q1", "expected_answer": "beta", "embedding": [1.0] + [0.0] * 127},
        {"question_id": "Q1", "expected_answer": "gamma", "embedding": [1.0] + [0.0] * 127},
    ]
    k0 = match_answer_key(0, "student text", keys, top_k=3)
    k2 = match_answer_key(2, "student text", keys, top_k=3)
    assert k0["expected_answer"] == "alpha"
    assert k2["expected_answer"] == "gamma"


def test_format_grading_context_side_by_side():
    key_hits = [
        {
            "chunk_id": "key_abc",
            "document_id": "keys_exam1",
            "text_content": "Model answer: photosynthesis converts light to chemical energy.",
            "meta": {"kind": "answer_key", "question_id": "Q1"},
        }
    ]
    sheet_hits = [
        {
            "chunk_id": "sheet_c1",
            "document_id": "sheet_s1",
            "text_content": "Student wrote about chloroplasts and sunlight.",
            "meta": {"kind": "sheet", "region_id": "R1", "source_page": 1},
        }
    ]
    out = format_grading_context(
        question_id="Q1",
        model_answer="Photosynthesis uses light.",
        student_ocr="chloroplasts sunlight",
        key_hits=key_hits,
        sheet_hits=sheet_hits,
        region_index=0,
    )
    text = out["context_text"]
    assert "KEY SIDE" in text
    assert "STUDENT SIDE" in text
    assert "Official model answer" in text
    assert "OCR text" in text
    assert "answer-key index" in text
    assert "sheet index" in text
    assert "photosynthesis" in text.lower()
    assert out["chunk_ids"]


def test_retrieve_context_for_grading_monkeypatch(monkeypatch):
    """Uses separate key and sheet searches (mocked)."""

    def fake_keys(exam_id, query, *, top_k=5):
        return [
            {
                "chunk_id": "key_k1",
                "text_content": "Q1 model text",
                "meta": {"kind": "answer_key", "question_id": "Q1"},
            }
        ]

    def fake_sheet_search(query, embedding, *, top_k=5, document_id=None):
        return [
            {
                "chunk_id": "sheet_s1",
                "text_content": "student patch text",
                "meta": {"kind": "sheet", "region_id": "R2"},
            }
        ]

    monkeypatch.setattr(
        "autograder.rag.retrieval.hybrid_search_for_keys",
        fake_keys,
    )
    monkeypatch.setattr(
        "autograder.rag.retrieval.hybrid_search_rag_chunks",
        fake_sheet_search,
    )

    key = {
        "id": "k1",
        "question_id": "Q1",
        "expected_answer": "Expected model",
        "max_marks": 4,
    }
    ctx = retrieve_context_for_grading(
        "sheet-1",
        "exam-1",
        "student ocr",
        key,
        top_k=3,
        region_index=1,
    )
    assert "KEY SIDE" in ctx["context_text"]
    assert "STUDENT SIDE" in ctx["context_text"]
    assert ctx["key_hit_count"] >= 1
    assert ctx["sheet_hit_count"] >= 1
    assert "keys_exam-1" in ctx["document_ids"][0] or "keys_" in str(ctx["document_ids"])
