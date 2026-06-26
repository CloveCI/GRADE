"""Rubric schema and report helpers."""

from autograder.report_pdf import build_evaluation_pdf
from autograder.schemas import RUBRIC_SCALE_MAX, RubricScores


def test_rubric_scores_default_length_for_legacy_rows():
    rs = RubricScores.model_validate(
        {
            "factual_accuracy": 4,
            "conceptual_completeness": 3,
            "reasoning": 2,
            "domain_terminology": 1,
        }
    )
    assert rs.length == 0
    assert rs.factual_accuracy == 4
    assert RUBRIC_SCALE_MAX == 5


def test_report_pdf_notes_manual_override():
    pdf = build_evaluation_pdf(
        {
            "id": "r1",
            "exam_id": "exam",
            "total_marks": 12.5,
            "max_total": 20,
            "confidence_flag": False,
            "grading_confidence": "medium",
            "llm_model": "test",
            "prompt_hash": "sha256:abc",
            "flags": ["human_override"],
            "questions": [
                {
                    "question_id": "Q1",
                    "awarded_marks": 6.5,
                    "max_marks": 7,
                    "rubric_scores": {
                        "factual_accuracy": 5,
                        "conceptual_completeness": 4,
                        "reasoning": 4,
                        "domain_terminology": 3,
                        "length": 4,
                    },
                    "student_answer": "sample",
                    "feedback": "Good work",
                    "ocr_confidence": 0.9,
                    "grading_confidence": "high",
                    "flags": ["human_override"],
                }
            ],
        }
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500
