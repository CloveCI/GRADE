"""
Answer key ingestion from Word ``.docx`` files (CIE-style keys with ``(N marks)`` blocks).
"""

from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

from autograder.schemas import AnswerKeyItemIn, UploadKeyRequest

logger = logging.getLogger(__name__)

_MARKS = re.compile(r"\((\d+(?:\.\d+)?)\s*marks?\)", re.IGNORECASE)
_PART = re.compile(r"\bPart\s+[A-Z]\b", re.IGNORECASE)
_SUBPART_STEM = re.compile(r"(?:^|\s)[(\[]?([a-z])[)\]]\s", re.IGNORECASE)


def extract_text_from_docx_bytes(data: bytes) -> str:
    """Plain text from ``word/document.xml`` (no external docx dependency)."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError) as e:
        raise ValueError(f"Invalid or empty DOCX: {e}") from e
    parts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)
    text = " ".join(parts)
    return re.sub(r"\s+", " ", text).strip()


def extract_text_from_docx_path(path: Path) -> str:
    return extract_text_from_docx_bytes(path.read_bytes())


def _strip_part_headers(text: str) -> str:
    return _PART.sub("", text).strip()


def _question_stem_from_raw(q_raw: str) -> str:
    q_lines = [s.strip() for s in re.split(r"(?<=[.?!])\s+", q_raw) if s.strip()]
    return q_lines[-1] if q_lines else q_raw


def _stem_letter(stem: str) -> Optional[str]:
    m = _SUBPART_STEM.search(stem.strip())
    return m.group(1).lower() if m else None


def _is_prompt_only_answer(answer: str) -> bool:
    """True when the gap after a marks block is only the next sub-part prompt (no model body)."""
    text = (answer or "").strip()
    if not text or len(text) > 360:
        return False
    if not re.match(r"^[(\[]?[a-z][)\]]\s", text, re.I):
        return False
    # Substantive model answers contain pseudocode / complexity notation, not just the part (b) stem.
    if re.search(
        r"(?:QUICKSORT|PARTITION\s*\(|DFS\s*\(|for\s+\w+\s*=\s*\d|while\s*\(|return\s+\w|O\s*\([^)]+\))",
        text,
        re.I,
    ):
        return False
    return True


def _merge_multipart_items(items: List[AnswerKeyItemIn]) -> List[AnswerKeyItemIn]:
    """
    Combine consecutive mark blocks that share one exam question (a) + (b) with a single answer region.

    CIE keys often place ``(3 marks)`` after part (a) and ``(4 marks)`` after part (b), but the model
    answer for both parts appears only after the second marker.
    """
    if len(items) < 2:
        return items

    merged: List[AnswerKeyItemIn] = []
    i = 0
    while i < len(items):
        cur = items[i]
        if i + 1 < len(items):
            nxt = items[i + 1]
            cur_parts = cur.expected_answer.split("\n\n", 1)
            nxt_parts = nxt.expected_answer.split("\n\n", 1)
            cur_stem = cur_parts[0] if cur_parts else ""
            cur_ans = cur_parts[1] if len(cur_parts) > 1 else ""
            nxt_stem = nxt_parts[0] if nxt_parts else ""
            nxt_ans = nxt_parts[1] if len(nxt_parts) > 1 else ""
            cur_letter = _stem_letter(cur_stem)
            nxt_letter = _stem_letter(nxt_stem)
            if (
                cur_letter == "a"
                and nxt_letter == "b"
                and _is_prompt_only_answer(cur_ans)
                and len(nxt_ans) > len(cur_ans) + 80
            ):
                combined_stem = f"{cur_stem}\n{nxt_stem}".strip()
                combined = f"{combined_stem}\n\n{nxt_ans}".strip()
                merged.append(
                    AnswerKeyItemIn(
                        question_id=f"Q{len(merged) + 1}",
                        expected_answer=combined,
                        max_marks=float(cur.max_marks) + float(nxt.max_marks),
                        domain=cur.domain,
                        rubric_override=cur.rubric_override,
                    )
                )
                i += 2
                continue
        merged.append(
            AnswerKeyItemIn(
                question_id=f"Q{len(merged) + 1}",
                expected_answer=cur.expected_answer,
                max_marks=cur.max_marks,
                domain=cur.domain,
                rubric_override=cur.rubric_override,
            )
        )
        i += 1
    return merged


def text_to_upload_request_cie(
    text: str,
    exam_id: str,
    default_max_marks: float = 4.0,
) -> UploadKeyRequest:
    """
    Parse CIE keys: ``Question prompt (N marks) Model answer …`` repeated.

    Each ``(N marks)`` ends the question line; following text is the model answer
    until the next marks marker.
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        raise ValueError("DOCX contained no extractable text")

    marks = list(_MARKS.finditer(text))
    if not marks:
        return UploadKeyRequest(
            exam_id=exam_id,
            questions=[
                AnswerKeyItemIn(
                    question_id="Q1",
                    expected_answer=text,
                    max_marks=default_max_marks,
                )
            ],
        )

    items: List[AnswerKeyItemIn] = []
    for i, m in enumerate(marks):
        prev_end = marks[i - 1].end() if i > 0 else 0
        q_raw = _strip_part_headers(text[prev_end : m.start()].strip())
        if i + 1 < len(marks):
            gap = text[m.end() : marks[i + 1].start()].strip()
            next_q_raw = _strip_part_headers(
                text[marks[i].end() : marks[i + 1].start()].strip()
            )
            next_q_lines = [
                s.strip() for s in re.split(r"(?<=[.?!])\s+", next_q_raw) if s.strip()
            ]
            next_stem = next_q_lines[-1] if next_q_lines else ""
            if next_stem and next_stem in gap:
                cut = gap.rfind(next_stem)
                answer = gap[:cut].strip() if cut > 0 else gap
            else:
                answer = gap
        else:
            answer = text[m.end() :].strip()
        try:
            mx = float(m.group(1))
        except ValueError:
            mx = default_max_marks
        if not answer:
            continue
        question_stem = _question_stem_from_raw(q_raw)
        combined = f"{question_stem}\n\n{answer}".strip()
        items.append(
            AnswerKeyItemIn(
                question_id=f"Q{len(items) + 1}",
                expected_answer=combined,
                max_marks=mx,
            )
        )

    if not items:
        raise ValueError("DOCX text had marks markers but no answer bodies were parsed")

    items = _merge_multipart_items(items)
    logger.info("CIE DOCX parsed into %s question(s) for exam_id=%s", len(items), exam_id)
    return UploadKeyRequest(exam_id=exam_id, questions=items)


def docx_bytes_to_upload_request(
    data: bytes,
    exam_id: str,
    default_max_marks: float = 4.0,
) -> UploadKeyRequest:
    raw = extract_text_from_docx_bytes(data)
    return text_to_upload_request_cie(raw, exam_id, default_max_marks)


def docx_path_to_upload_request(
    path: Path,
    exam_id: str,
    default_max_marks: float = 4.0,
) -> UploadKeyRequest:
    return docx_bytes_to_upload_request(path.read_bytes(), exam_id, default_max_marks)
