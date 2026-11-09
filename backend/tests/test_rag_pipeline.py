"""Unit tests for GRADE RAG query + key matching (no DB)."""

from autograder.rag.ingest import exam_rag_document_ids, keys_document_id, sheet_document_id
from autograder.rag.query import process_query
from autograder.rag.retrieval import match_answer_key


def test_process_query_normalizes():
    assert process_query("  What   is  LIFO?  ") == "What is LIFO"


def test_match_answer_key_by_index():
    keys = [
        {"question_id": "Q1", "expected_answer": "a", "max_marks": 2, "embedding": [0.1] * 128},
        {"question_id": "Q2", "expected_answer": "b", "max_marks": 2, "embedding": [0.2] * 128},
    ]
    k = match_answer_key(0, "anything", keys)
    assert k["question_id"] == "Q1"


def test_exam_rag_document_ids_pair_sheet_and_keys():
    assert exam_rag_document_ids("midterm", "sh1") == ["keys_midterm", "sheet_sh1"]
    assert keys_document_id("midterm") == "keys_midterm"
    assert sheet_document_id("sh1") == "sheet_sh1"
