# GRADE: what it is

> **Audience:** everyone · **Scope:** what GRADE does, who it is for, and what is true today · **Last verified:** 2026-11-08

## In one paragraph
GRADE (Generalized Recognition and Automated Document Evaluator) grades handwritten exam answer sheets. A teacher uploads a
marking scheme (answer key) and a scanned student sheet; GRADE splits each page into answer strips, reads the handwriting with
OCR, pairs each region with its answer-key question by position, and scores each question against a rubric with an LLM. The teacher reviews the
result in a web portal, can correct individual scores, and downloads a PDF report. It is a B.E. Computer Science academic mini
project (GRADE v2) by Md Afeeduddin and Syed Liyaqat, tuned for CIE-style internal exams with several questions per sheet.

## What is real today
| Capability | State | Notes |
|---|---|---|
| Answer-key upload (DOCX, JSON, text PDF) | Live | `key_docx.py`, `key_pdf.py`; scanned key PDFs need Google Vision |
| Sheet upload (PDF or image) | Live | Stored under `backend/data/uploads/`. The portal's job routes skip OCR at upload; the sync `/upload/sheet` and `/upload/exam-bundle` routes OCR and index the sheet immediately |
| Strip segmentation with per-exam layouts | Live | Presets `cie-daa`, `cie-dm` and others in `exam_layouts.py`; spanning answers merge across pages |
| Handwriting OCR | Live | Google Vision tier 1; Azure, PaddleOCR, TrOCR as fallbacks when installed and configured |
| Hybrid retrieval (pgvector + full-text) | Partial | Key excerpts work. Sheet excerpts exist only if the sheet was indexed (sync upload or `POST /api/sheet/{id}/ingest`); the portal's upload path never indexes it. MiniLM embeddings when `sentence-transformers` is installed, hash otherwise |
| LLM rubric scoring | Live when configured | Gemini, then OpenRouter; with `GRADE_ENABLE_LLM` off it uses a cosine-similarity fallback |
| Teacher review and score patch (HITL) | Live | `PATCH /result/{id}/questions/{region_index}` from the evaluator page |
| PDF report | Live | ReportLab, `report_pdf.py` |
| Hosted deployment | Not built | Runs on a developer machine; nothing deploys automatically |
| Authentication / multi-user access | Not built | The API has no auth; do not expose it to the internet |
| Measured grading accuracy | Partial | Sample sheets in `backend/cie/`; no published agreement metrics yet |

## What it is not
Not a hosted service, not a proctoring or plagiarism tool, and not a replacement for the examiner: every score is meant to be
reviewed, and the evaluator page exists for that.
