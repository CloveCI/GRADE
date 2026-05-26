"""OCR post-processing: heuristic + optional LLM formatting."""

from __future__ import annotations

from autograder.text_format import format_student_answer, _heuristic_format


def test_heuristic_fixes_common_garble():
    vocab = {"mitochondria", "photosynthesis", "respiration"}
    raw = "Uit . Resrouted as Staring date inline fos hin ove"
    out = _heuristic_format(raw, vocab)
    assert "for" in out.lower() or "fos" not in out.split()
    assert "  " not in out or out.count("  ") < raw.count("  ")


def test_format_passthrough_empty():
    r = format_student_answer("", {"question_id": "Q1", "expected_answer": "x"})
    assert r.formatted == ""
    assert "ocr_empty" in r.flags


def test_format_heuristic_only(monkeypatch):
    monkeypatch.delenv("GRADE_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GRADE_OCR_FORMAT_LLM", "0")
    monkeypatch.setenv("GRADE_ENABLE_LLM", "0")
    key = {"question_id": "Q1", "expected_answer": "photosynthesis in chloroplasts"}
    r = format_student_answer("teh proces of fotosynthesis", key)
    assert r.method == "heuristic"
    assert "the" in r.formatted.lower()
