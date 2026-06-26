"""GRADE RAG: sheet ingestion, hybrid retrieval, and key-aware context for grading."""

from autograder.rag.ingest import ingest_sheet_rag, sheet_document_id
from autograder.rag.query import QueryProcessor, process_query
from autograder.rag.retrieval import (
    hybrid_search_for_sheet,
    match_answer_key,
    retrieve_context_for_grading,
)

__all__ = [
    "QueryProcessor",
    "hybrid_search_for_sheet",
    "ingest_sheet_rag",
    "match_answer_key",
    "process_query",
    "retrieve_context_for_grading",
    "sheet_document_id",
]
