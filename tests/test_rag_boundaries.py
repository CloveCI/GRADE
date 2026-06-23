"""Bounded answer assembly from scoped RAG chunks."""

from autograder.rag.boundaries import (
    ChunkSpan,
    _trim_model_bleed,
    assemble_from_spans,
    extract_sheet_answer_span,
    is_multipart_question,
    pair_keys_with_regions,
    split_key_expected_answer,
)


def test_split_key_expected_answer():
    q, a = split_key_expected_answer("What is X?\n\nAn answer here.")
    assert q == "What is X?"
    assert a == "An answer here."


def test_assemble_from_spans_uses_char_positions():
    source = "abcdefghijklmnop"
    spans = [
        ChunkSpan("c0", 0, 0, 8, "abcdefgh", None),
        ChunkSpan("c1", 1, 6, 16, "ghijklmnop", None),
    ]
    out = assemble_from_spans(source, spans)
    assert out == "abcdefghijklmnop"


def test_trim_model_bleed_drops_next_question_stem():
    model = (
        "An algorithm is finite. It has input and output. "
        "Write General Abstraction for Divide and Conquer."
    )
    trimmed = _trim_model_bleed(model)
    assert "Divide and Conquer" not in trimmed
    assert "finite" in trimmed


def test_multipart_question_detects_a_and_b():
    expected = "a) Define X.\n\n(a) answer part a. (b) answer part b."
    assert is_multipart_question(expected)


def test_pair_keys_positional_page1_three_regions():
    keys = [
        {"question_id": "Q1", "sort_order": 0},
        {"question_id": "Q2", "sort_order": 1},
        {"question_id": "Q3", "sort_order": 2},
    ]
    regions = [
        {"region_id": "P1_R1", "text": "algorithm characteristics"},
        {"region_id": "P1_R2", "text": "divide and conquer"},
        {"region_id": "P1_R3", "text": "simple weighted union"},
    ]
    pairs = pair_keys_with_regions(keys, regions, regions_per_page=[3])
    assert len(pairs) == 3
    assert pairs[0][0]["question_id"] == "Q1"
    assert pairs[0][1]["region_id"] == "P1_R1"
    assert pairs[0][3] is True  # one_to_one


def test_extract_sheet_answer_span_finds_boundaries():
    ocr = (
        "Q1 intro noise. An algorithm is finite and has input output. "
        "Write General Abstraction for Divide and Conquer. "
        "Divide and conquer splits problems."
    )
    key = {
        "question_id": "Q1",
        "expected_answer": "State the characteristics.\n\nAn algorithm is finite.",
    }
    next_key = {
        "question_id": "Q2",
        "expected_answer": "Write General Abstraction for Divide and Conquer.\n\nDivide and conquer.",
    }
    start, end, text = extract_sheet_answer_span(ocr, key, next_key)
    assert start >= 0
    assert end > start
    assert "finite" in text.lower()
    assert "divide and conquer splits" not in text.lower()


def test_isolated_region_keeps_multipart_tail():
    """Isolated strips must not cut at in-answer vocabulary shared with the prompt."""
    ocr = (
        "4 , And a) A natural hazard is a potentially harmful event such as floods. "
        "Vulnerability refers to susceptibility. Risk arises when hazards affect vulnerable communities. "
        "Capacity development reduces risk by improving skills. "
        "b) Vulnerabilities are categorized as physical, social, economic, environmental, and institutional."
    )
    key = {
        "question_id": "Q4",
        "expected_answer": (
            "Define the relationship between natural hazards, vulnerability and risk. "
            "b) How will capacity development influence disaster risk?\n\n"
            "a) Natural hazards interact with vulnerability to produce risk."
        ),
    }
    _, _, text = extract_sheet_answer_span(ocr, key, None, isolated_region=True)
    assert "physical, social" in text.lower() or "categorized" in text.lower()
    assert len(text) > 120


def test_isolated_region_not_cut_by_next_question_keyword():
    """Q5 prompt word 'disasters' must not truncate Q4 when student writes 'disasters risk'."""
    ocr = (
        "4 , And a) A natural hazard is a potentially harmful event. Vulnerability refers to damage. "
        "Risk arises when hazards affect vulnerable communities. Thus, disasters risk depends on both "
        "hazards and vulnerability. Capacity development reduces risk. "
        "b) Vulnerabilities are categorized as physical, social, economic, environmental, and institutional."
    )
    key4 = {
        "question_id": "Q4",
        "expected_answer": (
            "Define hazards, vulnerability and risk. b) Capacity development.\n\nModel."
        ),
    }
    key5 = {
        "question_id": "Q5",
        "expected_answer": (
            "Discuss hydro-meteorological disasters in detail with examples.\n\nModel."
        ),
    }
    _, _, text = extract_sheet_answer_span(ocr, key4, key5, isolated_region=True)
    assert "capacity development" in text.lower()
    assert "categorized" in text.lower()


def test_prompt_stem_strip_uses_prefix_length_only():
    long_prompt = (
        "Define the relationship between natural hazards, vulnerability and risk in detail "
        "with examples from recent disasters and mitigation policy frameworks worldwide."
    )
    ocr = (
        f"{long_prompt[:55]} Student answer about hazards continues here with more detail "
        "about capacity development and vulnerability reduction measures."
    )
    key = {"question_id": "Q4", "expected_answer": f"{long_prompt}\n\nModel answer."}
    _, _, text = extract_sheet_answer_span(ocr, key, None, isolated_region=True)
    assert "capacity development" in text.lower()


def test_assemble_from_spans_merges_overlap():
    spans = [
        ChunkSpan("c0", 0, None, None, "hello world", None),
        ChunkSpan("c1", 1, None, None, "world again", None),
    ]
    out = assemble_from_spans("", spans)
    assert "hello world again" in out or out == "hello world again"
