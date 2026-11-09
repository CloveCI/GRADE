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


def test_format_rejects_truncated_llm_output(monkeypatch):
    from autograder import text_format as tf

    long_answer = (
        "Photosynthesis converts light energy into chemical energy in chloroplasts. "
        "The light reactions produce ATP and NADPH while the Calvin cycle fixes carbon dioxide "
        "into glucose through a series of enzyme-catalyzed steps in the stroma."
    )
    key = {
        "question_id": "Q1",
        "expected_answer": "Explain photosynthesis.\n\nPlants use chlorophyll.",
    }
    monkeypatch.setenv("GRADE_OCR_FORMAT_LLM", "1")
    monkeypatch.setenv("GRADE_ENABLE_LLM", "1")
    monkeypatch.setenv("GRADE_GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(tf, "_format_with_gemini", lambda *a, **k: long_answer[:80])
    r = format_student_answer(long_answer, key)
    assert r.method == "heuristic"
    assert "calvin cycle" in r.formatted.lower()
    assert "ocr_llm_truncated" in r.flags


def test_format_input_buffering_garble(monkeypatch):
    monkeypatch.setenv("GRADE_OCR_FORMAT_LLM", "0")
    monkeypatch.setenv("GRADE_ENABLE_LLM", "0")
    raw = (
        "Input buffering is a technique used in to improve the efficiency of reading Sourd "
        "in stead of reading one character at a time from characters into an the source file , "
        "the compiler reads a block Lace buffer. This General, two, buffers the number of input "
        "operations and increases Sped. General, I are used with Sential Characters to indicate "
        "the end of a buffer Bopert buffering the lexical, analyzer Scan tokens without repeadly, "
        "accessing file system . At also supports Onerall performance of look. - ahead operations "
        "needed during token recognition . Thus, input Buffering of reduces allinitasting in "
        "proase of developing a language the the alle. A simple in another ✓ the helps efficiently "
        "I the the Compiler proms mage"
    )
    key = {
        "question_id": "Q6",
        "expected_answer": "Write notes on Input Buffering.\n\nInput buffering improves lexical scan efficiency.",
    }
    r = format_student_answer(raw, key)
    low = r.formatted.lower()
    assert "bootstrapping" not in low
    assert "source" in low
    assert "instead" in low
    assert "sentinel" in low
    assert "repeatedly" in low
    assert "overall" in low
    assert "ocr_subpart_bleed_trimmed" in r.flags
    assert r.method == "heuristic"


def test_format_multipart_heuristic_fixes(monkeypatch):
    monkeypatch.setenv("GRADE_OCR_FORMAT_LLM", "0")
    monkeypatch.setenv("GRADE_ENABLE_LLM", "0")
    raw = (
        "4 , And a ) suck as a flood , eathquake . Risk arides when hazards affect witherable Communities . "
        "Thus ; disasters fisk depends . Expocity development reduces risk . "
        "6 ) Vulnerabilities are categorized as physical , epnomic , environmental ."
    )
    key = {
        "question_id": "Q4",
        "expected_answer": "a) Define hazards.\n\n(a) model a. (b) model b.",
    }
    r = format_student_answer(raw, key)
    assert r.method == "heuristic"
    low = r.formatted.lower()
    assert "such as" in low
    assert "earthquake" in low
    assert "arises" in low
    assert "vulnerable" in low
    assert "capacity" in low
    assert "b)" in low or "b )" not in low
    assert len(r.formatted) >= len(raw) * 0.85


# --- The OCR clean-up must not move the student's answer towards the model answer ---

import autograder.text_format as tf  # noqa: E402

_URBAN_KEY = {
    "question_id": "Q6",
    "expected_answer": (
        "Write a note on urban hazards.\n\nUrban hazards associate with accelerated urbanization and demographic "
        "expansion. Common threats include conflagrations, structural collapse and industrial accidents."
    ),
}
_URBAN_OCR = (
    "Urban hagards are risks associated with cities due to rapid urbanization and population growth. "
    "Common urban hazards include fires building collapse traffic accidents pollution floods."
)


def _openrouter_only(monkeypatch):
    monkeypatch.setenv("GRADE_OCR_FORMAT_LLM", "1")
    monkeypatch.setenv("GRADE_ENABLE_LLM", "1")
    monkeypatch.delenv("GRADE_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GRADE_OPENROUTER_API_KEY", "test-key")


def test_clean_up_prompt_does_not_contain_the_model_answer():
    from autograder.llm_providers import build_ocr_format_prompt

    prompt = build_ocr_format_prompt(_URBAN_OCR, _URBAN_KEY, "urbanization, hazards")
    assert "demographic expansion" not in prompt and "conflagrations" not in prompt
    assert "Write a note on urban hazards." in prompt  # the stem is still there
    assert "urbanization, hazards" in prompt


def test_clean_up_that_rewrites_in_key_wording_is_rejected(monkeypatch):
    _openrouter_only(monkeypatch)
    rewrite = (
        "Urban hazards associate with accelerated urbanization and demographic expansion. Common threats include "
        "conflagrations, structural collapse, traffic accidents, pollution and floods."
    )
    monkeypatch.setattr(tf, "_format_with_openrouter", lambda *a, **k: rewrite)
    out = tf.format_student_answer(_URBAN_OCR, _URBAN_KEY)
    assert out.method == "heuristic"
    assert "ocr_llm_rejected_key_drift" in out.flags
    assert "demographic" not in out.formatted and "conflagrations" not in out.formatted


def test_clean_up_that_only_fixes_spelling_is_kept(monkeypatch):
    _openrouter_only(monkeypatch)
    fixed = _URBAN_OCR.replace("hagards", "hazards").replace("fires building", "fires, building")
    monkeypatch.setattr(tf, "_format_with_openrouter", lambda *a, **k: fixed)
    out = tf.format_student_answer(_URBAN_OCR, _URBAN_KEY)
    assert out.method == "llm"
    assert out.formatted.startswith("Urban hazards are risks associated with cities")
