"""
Answer key ingestion from text-based PDFs.

Extracts text with pypdf and removes running headers/footers. Keys that label each model answer with
"Answer:" are parsed by question header (number, sub-part, Marks/CO/BTL, PART choice); other keys are split on
numbered sections (1. 2. Q1:, etc.).
"""

from __future__ import annotations

import logging
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from autograder.schemas import AnswerKeyItemIn, UploadKeyRequest

logger = logging.getLogger(__name__)


def extract_text_from_pdf_bytes(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("Install PyPDF to use PDF answer keys: pip install pypdf") from e

    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("Encrypted PDFs are not supported; provide an unlocked key PDF.") from exc
    chunks: List[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n\n".join(chunks).strip()


def ocr_pdf_bytes_to_text(data: bytes, *, max_pages: int = 20) -> str:
    """
    OCR a scanned/image-only PDF (no text layer) using the same tiered OCR stack as sheets.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError(
            "Scanned answer-key PDFs require PyMuPDF. Install: pip install pymupdf"
        ) from e

    from autograder.ocr import ocr_patch
    from autograder.preprocessing import load_bgr_from_path

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        path = Path(tmp.name)

    parts: List[str] = []
    try:
        doc = fitz.open(str(path))
        try:
            page_count = min(max(1, doc.page_count), max_pages)
        finally:
            doc.close()
        for page_idx in range(page_count):
            bgr = load_bgr_from_path(path, pdf_page_index=page_idx)
            result = ocr_patch(bgr)
            text = (result.text or "").strip()
            if text:
                parts.append(text)
    finally:
        path.unlink(missing_ok=True)

    return "\n\n".join(parts).strip()


def _parse_max_marks(body: str, default: float) -> Tuple[str, float]:
    for pat in (
        r"(?im)^\s*max\s*marks?\s*[:=]\s*(\d+(?:\.\d+)?)\s*$",
        r"(?im)max\s*marks?\s*[:=]\s*(\d+(?:\.\d+)?)",
    ):
        m = re.search(pat, body)
        if m:
            val = float(m.group(1))
            body = re.sub(pat, "", body, count=1).strip()
            return body, val
    return body, default


# Line-start: "1. ..." / "2) ..." / "Q3: ..." / "Question 4."
# Use horizontal whitespace only between the number and [.:)] so broken PDF text like
# "a\n2\n." (subscript indices) is not treated as a new section.
_HSP = r"[ \t\u00a0\u202f]*"
_SECTION_START = re.compile(
    rf"(?m)^[ \t]*(?:Q(?:uestion)?{_HSP}(\d+)|(\d+)){_HSP}[.:)]\s*",
    re.IGNORECASE,
)


def text_to_upload_request(text: str, exam_id: str, default_max_marks: float = 4.0) -> UploadKeyRequest:
    """
    Turn plain text (from PDF or else) into UploadKeyRequest.

    Splits on lines that start a new item: ``1.``, ``2)``, ``Q3:``, etc.
    If no numbered blocks are found, the entire text becomes a single question ``Q1``.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError(
            "Answer key PDF contained no extractable text after PDF extract and OCR "
            "(use a text-based key PDF/JSON, or configure Google Vision OCR in .env for scans)."
        )

    structured = _parse_answer_anchored_key(text, exam_id, default_max_marks)
    if structured is not None:
        return structured

    matches = list(_SECTION_START.finditer(text))
    if not matches:
        questions = [
            AnswerKeyItemIn(
                question_id="Q1",
                expected_answer=text,
                max_marks=default_max_marks,
            )
        ]
        return UploadKeyRequest(exam_id=exam_id, questions=questions)

    spans: List[Tuple[int, int, str]] = []
    for i, m in enumerate(matches):
        num = m.group(1) or m.group(2)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((m.start(), end, num))

    preamble = text[: spans[0][0]].strip()
    items: List[AnswerKeyItemIn] = []
    for idx, (start, end, num) in enumerate(spans):
        segment = text[start:end].strip()
        body = _SECTION_START.sub("", segment, count=1).strip()
        if idx == 0 and preamble:
            body = f"{preamble}\n\n{body}".strip()
        body, mx = _parse_max_marks(body, default_max_marks)
        items.append(
            AnswerKeyItemIn(
                question_id=f"Q{num}",
                expected_answer=body,
                max_marks=mx,
            )
        )
    items = _ensure_unique_question_ids(items)
    return UploadKeyRequest(exam_id=exam_id, questions=items)


# ---------------------------------------------------------------------------------------------------------------
# Structured keys: "N." / "a)" question headers with Marks-CO-BTL numbers, each followed by an "Answer:" label.
# ---------------------------------------------------------------------------------------------------------------

_ANSWER_ANCHOR = re.compile(r"(?m)^[ \t]*Answer[ \t]*:[ \t]*")
_QNUM_LINE = re.compile(r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,2})\s*[.)]\s*(.*)$", re.IGNORECASE)
_SUBPART_LINE = re.compile(r"^\s*\(?([a-h])\)\s*(.*)$", re.IGNORECASE)
_NUMBER_LINE = re.compile(r"^\s*(\d{1,3}(?:\.\d+)?)\s*$")
_INLINE_NUMBERS = re.compile(r"^(.*?\S)\s+(\d{1,3}(?:\.\d+)?)(?:\s+(\d{1,2}))?(?:\s+(\d{1,2}))?\s*$")
_PART = re.compile(
    r"(?im)^\s*PART\s*[-–—]?\s*([A-Z])\b[^\n(]*"
    r"(?:\(\s*(\d+)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)\s*marks?\s*\))?[^\n]*$"
)
_TABLE_HEAD = re.compile(r"(?i)^\s*(?:marks|co|btl|marks\s+co\s+btl|answer the following questions\s*:?.*)\s*$")
_APPENDIX = re.compile(
    r"(?im)^\s*(?:quick\s+revision|revision\s+(?:sheet|notes)|appendix\b|end\s+of\s+(?:the\s+)?(?:answer\s+)?key)"
)
_PAGE_NO = re.compile(r"(?i)^\s*page\s+\d+(?:\s+of\s+\d+)?\s*$")


def _strip_running_lines(page_texts: List[str]) -> List[str]:
    """
    Remove running headers/footers: lines in the first or last 3 lines of a page that repeat (digits ignored)
    on at least half of the pages, plus bare "Page N" lines. Single-page documents only lose "Page N".
    """
    pages = [p.splitlines() for p in page_texts]
    edge_counts: Dict[str, int] = {}
    for lines in pages:
        edges = {re.sub(r"\d+", "#", ln.strip()) for ln in lines[:3] + lines[-3:] if ln.strip()}
        for e in edges:
            edge_counts[e] = edge_counts.get(e, 0) + 1
    threshold = max(2, (len(pages) + 1) // 2)
    # Running headers have words; bare numbers (Marks/CO/BTL columns) and "Answer:" labels repeat legitimately.
    running = {
        e
        for e, n in edge_counts.items()
        if n >= threshold and not _ANSWER_ANCHOR.match(e) and len(re.findall(r"[A-Za-z]", e)) >= 4
    }
    out: List[str] = []
    for lines in pages:
        kept = []
        for i, ln in enumerate(lines):
            at_edge = i < 3 or i >= len(lines) - 3
            norm = re.sub(r"\d+", "#", ln.strip())
            if _PAGE_NO.match(ln) or (at_edge and norm in running):
                continue
            kept.append(ln)
        out.append("\n".join(kept))
    return out


def _header_start(segment: str, *, max_lines: int = 12) -> Tuple[int, Optional[re.Match], Optional[re.Match]]:
    """
    Locate the question header at the end of ``segment`` (the text just before an "Answer:" label).

    Returns ``(offset, qnum_match, subpart_match)``. The header is the closest question-number or sub-part line,
    so numbered lists inside the previous answer ("1. Natural hazard") are never taken for questions.
    """
    lines = segment.splitlines(keepends=True)
    offsets = []
    pos = 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln)
    seen = 0
    for i in range(len(lines) - 1, -1, -1):
        text = lines[i].strip()
        if not text:
            continue
        seen += 1
        if seen > max_lines:
            break
        sub = _SUBPART_LINE.match(text)
        if sub:
            # "4." on its own just above "a)" belongs to the same header
            for j in range(i - 1, -1, -1):
                prev = lines[j].strip()
                if not prev or _TABLE_HEAD.match(prev):
                    continue
                qn = _QNUM_LINE.match(prev)
                if qn and not qn.group(2).strip():
                    return offsets[j], qn, sub
                break
            return offsets[i], None, sub
        qn = _QNUM_LINE.match(text)
        if qn:
            return offsets[i], qn, None
    return len(segment), None, None


def _parse_header(header: str, qnum: Optional[re.Match], sub: Optional[re.Match]) -> Tuple[str, Optional[float]]:
    """Question text and marks from a header block (the Marks / CO / BTL numbers follow the question text)."""
    lines = [ln.strip() for ln in header.splitlines() if ln.strip() and not _TABLE_HEAD.match(ln)]
    if lines and qnum and _QNUM_LINE.match(lines[0]):
        rest = _QNUM_LINE.match(lines[0]).group(2).strip()
        lines = ([rest] if rest else []) + lines[1:]
    if lines and sub and _SUBPART_LINE.match(lines[0]):
        rest = _SUBPART_LINE.match(lines[0]).group(2).strip()
        lines = ([rest] if rest else []) + lines[1:]
    numbers: List[str] = []
    while lines and _NUMBER_LINE.match(lines[-1]) and len(numbers) < 3:
        numbers.insert(0, _NUMBER_LINE.match(lines[-1]).group(1))
        lines.pop()
    if not numbers and lines:
        m = _INLINE_NUMBERS.match(lines[-1])
        if m and m.group(3):  # need marks + CO (+ BTL) so a question ending in a year is not misread
            numbers = [g for g in m.groups()[1:] if g]
            lines[-1] = m.group(1)
    marks = float(numbers[0]) if numbers else None
    return " ".join(lines).strip(), marks


def _clean_body(body: str) -> str:
    kept = [ln for ln in body.splitlines() if not _PART.match(ln) and not _TABLE_HEAD.match(ln)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def _parse_answer_anchored_key(
    text: str, exam_id: str, default_max_marks: float
) -> Optional[UploadKeyRequest]:
    """Parse keys laid out as question header → "Answer:" → model answer. ``None`` when the layout does not apply."""
    anchors = list(_ANSWER_ANCHOR.finditer(text))
    if len(anchors) < 2:
        return None
    appendix = _APPENDIX.search(text, anchors[-1].end())
    text_end = appendix.start() if appendix else len(text)

    headers = []  # (start, end, qnum_match, sub_match)
    prev_end = 0
    for a in anchors:
        seg = text[prev_end : a.start()]
        off, qn, sub = _header_start(seg)
        headers.append((prev_end + off, a.start(), qn, sub))
        prev_end = a.end()
    if not any(h[2] for h in headers):
        return None

    parts = []  # dicts: num, sub, question, marks, body, section
    current_num: Optional[str] = None
    for k, (h_start, h_end, qn, sub) in enumerate(headers):
        if qn:
            current_num = qn.group(1)
        elif current_num is None:
            current_num = str(len({p["num"] for p in parts}) + 1)
        question, marks = _parse_header(text[h_start:h_end], qn, sub)
        body_end = headers[k + 1][0] if k + 1 < len(headers) else text_end
        body = _clean_body(text[anchors[k].end() : body_end])
        section = None
        for m in _PART.finditer(text, 0, h_start):
            section = m
        parts.append(
            {
                "num": current_num,
                "sub": sub.group(1).lower() if sub else None,
                "question": question,
                "marks": marks,
                "body": body,
                "section": section,
            }
        )

    grouped: Dict[str, List[dict]] = {}
    for p in parts:
        grouped.setdefault(p["num"], []).append(p)

    # A part counts "n of m" when it lists more questions than its printed (n x marks) header says to answer.
    section_sizes: Dict[str, int] = {}
    for ps in grouped.values():
        sec = ps[0]["section"]
        if sec:
            section_sizes[sec.group(1).upper()] = section_sizes.get(sec.group(1).upper(), 0) + 1

    items: List[AnswerKeyItemIn] = []
    for num, ps in grouped.items():
        if len(ps) == 1 and not ps[0]["sub"]:
            expected = f"{ps[0]['question']}\n\n{ps[0]['body']}".strip()
        else:
            expected = "\n\n".join(f"{p['sub'] or '?'}) {p['question']}\n{p['body']}".strip() for p in ps)
        marks = sum(p["marks"] if p["marks"] is not None else default_max_marks for p in ps)
        sec = ps[0]["section"]
        section = sec.group(1).upper() if sec else None
        pick = int(sec.group(2)) if sec and sec.group(2) else None
        if section and pick is not None and section_sizes.get(section, 0) <= pick:
            pick = None  # every question in this part counts
        items.append(
            AnswerKeyItemIn(
                question_id=f"Q{num}",
                expected_answer=expected,
                max_marks=marks,
                section=section,
                section_pick=pick,
            )
        )
    logger.info(
        "Structured key parsed: %s question(s) from %s answer block(s) for exam_id=%s",
        len(items),
        len(parts),
        exam_id,
    )
    return UploadKeyRequest(exam_id=exam_id, questions=_ensure_unique_question_ids(items))


def _ensure_unique_question_ids(items: List[AnswerKeyItemIn]) -> List[AnswerKeyItemIn]:
    """
    Scanned keys often repeat ``1.`` / ``Q1`` for every block; renumber to Q1..Qn in order.
    """
    if len(items) <= 1:
        return items
    ids = [it.question_id for it in items]
    if len(set(ids)) == len(ids):
        return items
    logger.info(
        "Duplicate question_id values %s; renumbering to Q1..Q%s by section order",
        ids,
        len(items),
    )
    return [it.model_copy(update={"question_id": f"Q{i + 1}"}) for i, it in enumerate(items)]


def extract_text_per_pdf_page(data: bytes) -> List[str]:
    """One text blob per PDF page (text layer or empty)."""
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("Install PyPDF to use PDF answer keys: pip install pypdf") from e

    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("Encrypted PDFs are not supported; provide an unlocked key PDF.") from exc
    return [(page.extract_text() or "").strip() for page in reader.pages]


def pdf_bytes_to_upload_request(
    data: bytes,
    exam_id: str,
    default_max_marks: float = 4.0,
) -> UploadKeyRequest:
    page_texts = _strip_running_lines(extract_text_per_pdf_page(data))
    raw = "\n\n".join(t for t in page_texts if t).strip()
    if not raw:
        logger.info("Key PDF has no text layer; attempting OCR fallback exam_id=%s", exam_id)
        try:
            raw = ocr_pdf_bytes_to_text(data)
            page_texts = [raw] if raw.strip() else []
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning("Key PDF OCR fallback failed: %s", e)
            raw = ""
            page_texts = []

    req = text_to_upload_request(raw, exam_id, default_max_marks)
    if len(req.questions) == 1 and len([t for t in page_texts if t]) > 1:
        items: List[AnswerKeyItemIn] = []
        for i, text in enumerate(page_texts):
            if not text.strip():
                continue
            body, mx = _parse_max_marks(text.strip(), default_max_marks)
            items.append(
                AnswerKeyItemIn(
                    question_id=f"Q{len(items) + 1}",
                    expected_answer=body,
                    max_marks=mx,
                )
            )
        if items:
            logger.info(
                "Key PDF split into %s page-based question(s) for exam_id=%s",
                len(items),
                exam_id,
            )
            return UploadKeyRequest(exam_id=exam_id, questions=items)
    return req
