"""Query normalization for hybrid RAG (adapted from repo ``search/query_processor.py``)."""

from __future__ import annotations

import re
from typing import List

_STOP = frozenset(
    {"a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from", "is", "are", "was", "were"}
)


class QueryProcessor:
    def __init__(self, remove_stop_words: bool = False) -> None:
        self.remove_stop_words = remove_stop_words

    def process(self, query: str) -> str:
        if not query:
            return ""
        query = re.sub(r"\s+", " ", query).strip()
        query = re.sub(r"[^\w\s\-.]", " ", query)
        if self.remove_stop_words:
            query = " ".join(w for w in query.lower().split() if w not in _STOP)
        return re.sub(r"\s+", " ", query).strip()

    def extract_keywords(self, query: str) -> List[str]:
        words = self.process(query).lower().split()
        return [w for w in words if w not in _STOP and len(w) > 2]


_processor = QueryProcessor()


def process_query(query: str) -> str:
    return _processor.process(query)
