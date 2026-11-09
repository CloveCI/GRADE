"""Answer key text / PDF parsing helpers."""

from __future__ import annotations

import pytest

from autograder.key_pdf import pdf_bytes_to_upload_request, text_to_upload_request


def test_text_single_block_becomes_q1():
    r = text_to_upload_request("Paris is the capital of France.", "exam-a", 5.0)
    assert r.exam_id == "exam-a"
    assert len(r.questions) == 1
    assert r.questions[0].question_id == "Q1"
    assert r.questions[0].max_marks == 5.0
    assert "Paris" in r.questions[0].expected_answer


def test_text_numbered_sections():
    raw = "Preamble before.\n\n1. First model answer.\n\n2. Second model answer.\n"
    r = text_to_upload_request(raw, "exam-b", 4.0)
    assert len(r.questions) == 2
    assert r.questions[0].question_id == "Q1"
    assert "Preamble" in r.questions[0].expected_answer
    assert "First model" in r.questions[0].expected_answer
    assert r.questions[1].question_id == "Q2"
    assert "Second model" in r.questions[1].expected_answer


def test_max_marks_inline():
    t = "1. Alpha answer.\nMax marks: 10\n\n2. Beta.\n"
    r = text_to_upload_request(t, "e", 4.0)
    assert r.questions[0].max_marks == 10.0
    assert r.questions[1].max_marks == 4.0


def test_empty_text_raises():
    with pytest.raises(ValueError, match="no extractable"):
        text_to_upload_request("", "e", 4.0)


def test_section_marker_does_not_span_lines():
    """Avoid treating subscript-like line breaks (a\\n2\\n.) as a numbered section 2."""
    raw = (
        "1. First answer block.\n"
        "formula (a1,\n"
        "a\n"
        "2\n"
        ".,an)\n\n"
        "2. Second answer block.\n"
    )
    r = text_to_upload_request(raw, "e", 4.0)
    assert len(r.questions) == 2
    assert r.questions[0].question_id == "Q1"
    assert "First answer" in r.questions[0].expected_answer
    assert r.questions[1].question_id == "Q2"
    assert "Second answer" in r.questions[1].expected_answer


def test_multi_page_pdf_splits_into_q1_q2_when_no_numbered_sections():
    pytest.importorskip("pypdf")
    from io import BytesIO

    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Page one model answer about stacks.")
    c.showPage()
    c.drawString(72, 720, "Page two model answer about disks.")
    c.save()
    r = pdf_bytes_to_upload_request(buf.getvalue(), "exam-pages", 4.0)
    assert len(r.questions) == 2
    assert r.questions[0].question_id == "Q1"
    assert r.questions[1].question_id == "Q2"
    assert "stacks" in r.questions[0].expected_answer.lower()
    assert "disks" in r.questions[1].expected_answer.lower()


def test_duplicate_section_numbers_renumbered():
    raw = "1. First answer.\n\n1. Second answer.\n\n1. Third answer.\n"
    r = text_to_upload_request(raw, "exam-dup", 4.0)
    assert len(r.questions) == 3
    assert [q.question_id for q in r.questions] == ["Q1", "Q2", "Q3"]
    assert "First" in r.questions[0].expected_answer
    assert "Second" in r.questions[1].expected_answer
    assert "Third" in r.questions[2].expected_answer


def test_pdf_via_reportlab_extracts_sections():
    pytest.importorskip("reportlab")
    pytest.importorskip("pypdf")
    from io import BytesIO

    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "1. First model answer for exam.")
    c.drawString(72, 680, "2. Second model answer here.")
    c.save()
    data = buf.getvalue()
    r = pdf_bytes_to_upload_request(data, "rlexam", 3.0)
    assert r.exam_id == "rlexam"
    assert len(r.questions) == 2
    assert "First model" in r.questions[0].expected_answer
    assert "Second model" in r.questions[1].expected_answer


# --- Structured keys: question header with Marks/CO/BTL, then "Answer:" (e.g. the reformatted CIE model answer key) ---

_STRUCTURED_PAGES = [
    "OE 601 CE | Disaster Mitigation | CIE-I | Model Answer Key\nPage 1\nCOLLEGE NAME\n[Max Marks: 20]\n"
    "PART - A (3x2 = 6 Marks)\nAnswer the following questions:\nMarks\nCO\nBTL\n"
    "1.\nList the classification of disasters\n2\n2\n2\nAnswer:\nNatural and human-induced disasters.\n"
    "2.\nDifferentiate between Hazard and Disaster\n2\n1\n3\nAnswer:\nA hazard is potential harm.",
    "OE 601 CE | Disaster Mitigation | CIE-I | Model Answer Key\nPage 2\n"
    "3.\nDefine Vulnerability and Resilience\n2\n1\n2\nAnswer:\nVulnerability is susceptibility.\n"
    "PART - B (2x7 = 14 Marks)\nMarks\nCO\nBTL\n"
    "4.\na)\nDefine the relationship between hazards and risk.\n4\n1\n3\nAnswer:\n"
    "1. Natural hazard\nA damaging event.\n2. Vulnerability\nSusceptibility.\n3. Risk\nPotential loss.\n"
    "b)\nHow can you categorize vulnerabilities?\n3\n1\n3\nAnswer:\nPhysical, social, economic.",
    "OE 601 CE | Disaster Mitigation | CIE-I | Model Answer Key\nPage 3\n"
    "5.\nDiscuss hydro meteorological disasters.\n7\n2\n3\nAnswer:\nFloods, cyclones, droughts.\n"
    "6.\na)\nWrite a note on urban hazards?\n3\n2\n3\nAnswer:\nUrban floods and fires.\n"
    "b)\nDiscuss Bhopal Gas Tragedy.\n4\n2\n3\nAnswer:\nMIC leak in 1984.\n"
    "QUICK REVISION SHEET\n1. Core terms\nHazard Potential source of harm.\n2. Disaster-management cycle\nEnd of Answer Key",
]


def _structured_request():
    from autograder.key_pdf import _strip_running_lines, text_to_upload_request

    text = "\n\n".join(_strip_running_lines(_STRUCTURED_PAGES))
    return text_to_upload_request(text, "cie-dism", default_max_marks=4.0)


def test_structured_key_finds_the_six_printed_questions():
    req = _structured_request()
    assert [q.question_id for q in req.questions] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
    assert [q.max_marks for q in req.questions] == [2, 2, 2, 7, 7, 7]  # 4a+4b, 6a+6b summed


def test_numbered_lists_inside_answers_are_not_questions():
    q4 = _structured_request().questions[3].expected_answer
    assert "1. Natural hazard" in q4 and "3. Risk" in q4
    assert q4.startswith("a) Define the relationship") and "\n\nb) How can you categorize" in q4


def test_preamble_headers_appendix_and_part_lines_are_dropped():
    req = _structured_request()
    joined = "\n".join(q.expected_answer for q in req.questions)
    for leak in ("Model Answer Key", "Page 2", "Max Marks", "PART", "QUICK REVISION", "Core terms", "End of Answer Key", "\nCO\n"):
        assert leak not in joined, leak
    assert req.questions[0].max_marks == 2  # the header's "[Max Marks: 20]" is not Q1's marks


def test_part_with_choice_records_best_n_of_m():
    req = _structured_request()
    assert [(q.section, q.section_pick) for q in req.questions] == [
        ("A", None), ("A", None), ("A", None), ("B", 2), ("B", 2), ("B", 2),
    ]


def test_running_header_stripping_keeps_repeated_answer_labels():
    from autograder.key_pdf import _strip_running_lines

    pages = ["Header | Key\nPage 1\nAnswer:\nx", "Header | Key\nPage 2\nAnswer:\ny"]
    out = _strip_running_lines(pages)
    assert out == ["Answer:\nx", "Answer:\ny"]


def test_plain_numbered_key_still_uses_the_simple_splitter():
    from autograder.key_pdf import text_to_upload_request

    req = text_to_upload_request("1. Photosynthesis uses light.\n2. Mitosis divides cells.", "bio")
    assert [q.question_id for q in req.questions] == ["Q1", "Q2"]
    assert req.questions[0].section is None
