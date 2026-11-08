"""CIE DOCX answer key parsing."""

from pathlib import Path

import pytest

from autograder.key_docx import docx_path_to_upload_request, extract_text_from_docx_path

REPO = Path(__file__).resolve().parents[1]


def test_daa_docx_parses_multiple_questions():
    path = REPO / "cie" / "keys" / "DAA.docx"
    if not path.is_file():
        pytest.skip("cie/keys/DAA.docx not in workspace")
    text = extract_text_from_docx_path(path)
    assert "marks" in text.lower()
    req = docx_path_to_upload_request(path, "cie-daa")
    assert len(req.questions) == 6
    assert req.questions[0].question_id == "Q1"
    assert req.questions[0].max_marks >= 2


def test_daa_multipart_questions_merge_a_and_b():
    path = REPO / "cie" / "keys" / "DAA.docx"
    if not path.is_file():
        pytest.skip("cie/keys/DAA.docx not in workspace")
    req = docx_path_to_upload_request(path, "cie-daa")
    q5 = req.questions[4]
    assert q5.max_marks == 7.0
    assert "a)" in q5.expected_answer.lower()
    assert "b)" in q5.expected_answer.lower()
    assert "QUICKSORT" in q5.expected_answer.upper()
    assert "Merge Sort" in q5.expected_answer or "merge sort" in q5.expected_answer.lower()
