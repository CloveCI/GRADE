# GRADE: what it is

> **Audience:** everyone · **Scope:** what GRADE does, who it is for, and what is true today · **Last verified:** 2026-11-09

## In one paragraph
GRADE (Generalized Recognition and Automated Document Evaluator) grades handwritten exam answer sheets. A teacher uploads a
marking scheme (answer key) and a scanned student sheet; GRADE finds each answer on the sheet using the marking scheme, reads the
handwriting with OCR, pairs answer *n* with question *n*, and scores each question against a rubric with an LLM. The teacher reviews the
result in a web portal, can correct individual scores, and downloads a PDF report. It is a B.E. Computer Science academic mini
project (GRADE v2) by Md Afeeduddin and Syed Liyaqat, tuned for CIE-style internal exams with several questions per sheet.

## What is real today
| Capability | State | Notes |
|---|---|---|
| Answer-key upload (DOCX, JSON, text PDF) | Live | Structured PDF keys (question header + `Answer:`) parsed by header, with PART choice sections; scanned key PDFs need Google Vision |
| Choice sections ("any 2 of 3") | Live for PDF keys | Best answers counted, paper maximum respected; the DOCX parser does not read PART lines yet |
| Sheet upload (PDF or image) | Live | Stored under `backend/data/uploads/`. The portal's job routes skip OCR at upload; the sync `/upload/sheet` and `/upload/exam-bundle` routes OCR and index the sheet immediately |
| Answer layout (where each answer is) | Live | Automatic from page OCR lines, margin labels and the model answers (needs PaddleOCR); 17 of 18 boundaries right on three CIE samples. A layout the teacher enters overrides it |
| Handwriting OCR | Live | Google Vision tier 1 (not yet validated); Azure, PaddleOCR (2.x and 3.x), TrOCR as fallbacks. Local PaddleOCR reads CIE handwriting at confidence 0.70-0.77: readable but noisy |
| Matching answers to questions | Partial | By position: answer *n* is graded against question *n*. Skipped or out-of-order answers are graded against the wrong question |
| Hybrid retrieval (pgvector + full-text) | Live | Evaluate indexes the OCR it grades; KEY SIDE limited to the graded question. MiniLM embeddings when `sentence-transformers` is installed, hash otherwise |
| LLM rubric scoring | Live when configured | Gemini, then OpenRouter (validated with `google/gemini-2.5-flash-lite`); with `GRADE_ENABLE_LLM` off, or every provider failing, a cosine-similarity fallback labelled `fallback-legacy` |
| OCR clean-up before grading | Live | Heuristics plus an optional LLM pass that never sees the model answer; rewrites towards the key are rejected |
| Portal UI (GRADE Companion) | Baseline | Working pages for upload, grading, review and reports; not covered by the v2 validation |
| Teacher review and score patch (HITL) | Live | `PATCH /result/{id}/questions/{region_index}` from the evaluator page |
| PDF report | Live | ReportLab, `report_pdf.py` |
| Hosted deployment | Not built | Runs on a developer machine; nothing deploys automatically |
| Authentication / multi-user access | Not built | The API has no auth; do not expose it to the internet |
| Measured grading accuracy | Not measured | One sheet graded end to end (16.8 / 20); no comparison with a human examiner yet |

## How far to trust a result
A first-pass grade for a teacher to review. The evidence behind each "Live" above, what was not tested, and a checklist for
reviewing a grade are in [`operations/validation.md`](operations/validation.md).

## What it is not
Not a hosted service, not a proctoring or plagiarism tool, and not a replacement for the examiner: every score is meant to be
reviewed, and the evaluator page exists for that.
