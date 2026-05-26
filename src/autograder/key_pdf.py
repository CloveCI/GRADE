"""
Answer key ingestion from text-based PDFs.

Extracts text with pypdf, then splits on numbered sections (1. 2. Q1:, etc.).
"""

from __future__ import annotations

import logging
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

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
    return UploadKeyRequest(exam_id=exam_id, questions=items)


def pdf_bytes_to_upload_request(
    data: bytes,
    exam_id: str,
    default_max_marks: float = 4.0,
) -> UploadKeyRequest:
    raw = extract_text_from_pdf_bytes(data)
    if not raw.strip():
        logger.info("Key PDF has no text layer; attempting OCR fallback exam_id=%s", exam_id)
        try:
            raw = ocr_pdf_bytes_to_text(data)
        except RuntimeError:
            raise
        except Exception as e:
            logger.warning("Key PDF OCR fallback failed: %s", e)
            raw = ""
    return text_to_upload_request(raw, exam_id, default_max_marks)
