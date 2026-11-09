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


def test_format_grading_context_never_cuts_the_student_answer():
    """A 7-mark key (~3.5k chars) plus a long answer used to be sliced at max_chars + 400, so the LLM got no answer."""
    model = "Hydro-meteorological disasters are caused by atmospheric processes. " * 55  # ~3.7k chars
    student = ("floods cyclones droughts heat waves early warning. " * 24) + "FINAL_STUDENT_WORDS"
    excerpt = {
        "chunk_id": "key_x",
        "document_id": "keys_exam1",
        "text_content": "Model answer excerpt: shelters and evacuation. " * 10,
        "meta": {"kind": "answer_key", "question_id": "Q5"},
    }
    out = format_grading_context(
        question_id="Q5",
        model_answer=model,
        student_ocr=student,
        key_hits=[excerpt],
        sheet_hits=[],
        max_chars=3200,
    )
    text = out["context_text"]
    assert model.strip() in text
    assert "FINAL_STUDENT_WORDS" in text
    assert "=== INSTRUCTIONS ===" in text
    # the excerpt budget is what gives way when the essentials are long
    assert "shelters and evacuation" not in text
    assert "(no additional key chunks retrieved)" in text


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


def test_key_side_keeps_only_the_graded_question(monkeypatch):
    """Other questions' model answers must not appear under 'Question N' (seen on all 6 Disaster Mitigation questions)."""

    def fake_keys(exam_id, query, *, top_k=5):
        return [
            {"chunk_id": "key_q2a", "text_content": "Q2 hazard vs disaster", "similarity": 0.8, "meta": {"kind": "answer_key", "question_id": "Q2"}},
            {"chunk_id": "key_q1a", "text_content": "Q1 classification", "similarity": 0.7, "meta": {"kind": "answer_key", "question_id": "Q1"}},
            {"chunk_id": "key_q4a", "text_content": "Q4 risk relationship", "similarity": 0.6, "meta": {"kind": "answer_key", "question_id": "Q4"}},
        ]

    monkeypatch.setattr("autograder.rag.retrieval.hybrid_search_for_keys", fake_keys)
    monkeypatch.setattr("autograder.rag.retrieval.list_rag_chunks_for_corpus", lambda *a, **k: [])
    monkeypatch.setattr("autograder.rag.retrieval.hybrid_search_rag_chunks", lambda *a, **k: [])
    ctx = retrieve_context_for_grading("s1", "exam1", "a hazard is", {"id": "k2", "question_id": "Q2", "expected_answer": "x"})
    assert [h["chunk_id"] for h in ctx["key_hits"]] == ["key_q2a"]
    assert "Q1 classification" not in ctx["context_text"]
    assert "Q4 risk relationship" not in ctx["context_text"]


def test_key_side_falls_back_to_the_questions_own_chunks(monkeypatch):
    calls = {}

    def fake_list(document_id, **kwargs):
        calls["doc"], calls["qid"] = document_id, kwargs.get("question_id")
        return [{"chunk_id": "key_q5", "text_content": "Q5 model", "meta": {"kind": "answer_key", "question_id": "Q5"}}] if document_id.startswith("keys_") else []

    monkeypatch.setattr(
        "autograder.rag.retrieval.hybrid_search_for_keys",
        lambda *a, **k: [{"chunk_id": "key_q1", "text_content": "Q1", "meta": {"kind": "answer_key", "question_id": "Q1"}}],
    )
    monkeypatch.setattr("autograder.rag.retrieval.list_rag_chunks_for_corpus", fake_list)
    monkeypatch.setattr("autograder.rag.retrieval.hybrid_search_rag_chunks", lambda *a, **k: [])
    ctx = retrieve_context_for_grading("s1", "exam1", "floods", {"id": "k5", "question_id": "Q5", "expected_answer": "x"})
    assert [h["chunk_id"] for h in ctx["key_hits"]] == ["key_q5"]


def test_fts_match_survives_similarity_cutoff():
    from autograder.rag.similarity import filter_hits_by_threshold

    hits = [
        {"chunk_id": "noisy_ocr_bhopal", "similarity": 0.32, "fts_match": True},
        {"chunk_id": "unrelated", "similarity": 0.20},
        {"chunk_id": "strong", "similarity": 0.60},
    ]
    kept = [h["chunk_id"] for h in filter_hits_by_threshold(hits, threshold=0.35)]
    assert kept == ["noisy_ocr_bhopal", "strong"]


def test_fts_query_is_ored_and_sanitised():
    from autograder.db import _fts_or_query

    assert _fts_or_query("Question Q4 model answer reference: Risk = Hazard & Vulnerability!") == (
        "question | q4 | model | answer | reference | risk | hazard | vulnerability"
    )
    assert _fts_or_query("') | !! & :*") == ""
