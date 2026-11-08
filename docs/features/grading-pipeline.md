# Grading pipeline

> **Audience:** developers changing how sheets are segmented, read or scored · **Scope:** what happens from upload to report,
> status, data, failure modes · **Last verified:** 2026-11-08 (`api.py`, `jobs.py`, `evaluation_service.py`, `scoring.py`, `ocr.py`)

## Status
Works end to end on the bundled CIE samples (`backend/cie/`) with Google Vision and Gemini configured. Without credentials it
still runs: OCR falls through to whatever local engines are installed, and scoring uses the cosine-similarity fallback, which is
only a rough signal. Agreement with human examiners has not been measured.

## How it works
1. **Key upload.** DOCX, JSON or text PDF is parsed into one row per question with model answer and max marks
   (`key_docx.py`, `key_pdf.py`), then chunked and embedded for retrieval (`key_chunks.py`, `rag/ingest.py`).
2. **Sheet upload.** The file is saved to `data/uploads/sheet_*.pdf` and a `sheets` row is created. OCR and RAG ingest are
   **deferred** to evaluate, so upload is fast (`sheet_ingest: deferred`).
3. **Cache check.** `run_evaluation()` returns the latest stored result for the sheet and exam (`existing_evaluate_response`)
   unless `force_regrade` is set, the number of keys changed, the resolved layout differs (`layout:` flag), or the result
   predates `segmentation_v3`.
4. **Layout.** `resolve_regions_per_page()` takes the request's layout, else the exam preset, else infers from the key count
   (`exam_layouts.py`). Example: `cie-daa` = `3,1,2,1`, with Q4 merged from strips on pages 2 and 3.
5. **Segment.** `preprocess_sheet_for_evaluation()` renders pages at `GRADE_PDF_RENDER_SCALE` (default 3.0), deskews, finds
   ink-aware strip boundaries, and merges strips into question regions. Regions are stored in `sheets.question_regions`
   and rendered as previews (`sheet_preview.py`).
6. **OCR.** `ocr_patch()` tiles very tall patches, then tries Google Vision (`DOCUMENT_TEXT_DETECTION`), Azure, PaddleOCR, TrOCR
   in order, returning text, confidence and the engine used. `GRADE_OCR_GOOGLE_ONLY` / `GRADE_OCR_CLOUD_ONLY` narrow the chain.
7. **Retrieve and trim.** `retrieve_context_for_grading()` combines pgvector similarity and full-text search over key chunks;
   `rag/boundaries.py` trims text belonging to the neighbouring question.
8. **Score.** `score_answer_llm()`: if `GRADE_ENABLE_LLM` is off → legacy cosine score; else `GRADE_LLM_MOCK_RESPONSE` (tests) →
   Gemini → OpenRouter → legacy. The prompt is `prompts/grading_v2.txt`; the output is rubric JSON with marks, feedback and
   confidence.
9. **Persist.** Per-question answers go to `sheet_question_answers`; the whole result, with prompt hash and model label, goes to
   `evaluation_results`.
10. **Review.** The evaluator page shows each region over its page image; a teacher can patch a question's marks and feedback.
11. **Report.** `GET /report/{id}/pdf` builds the ReportLab PDF.

## Data
| Table / path | What it holds |
|---|---|
| `answer_keys` | question id, model answer, max marks, sort order, per exam |
| `answer_key_chunks`, `rag_chunks` | embedded text chunks (128-D hash vectors by default) with FTS |
| `sheets` | file path, exam id, `question_regions` JSONB |
| `sheet_question_answers` | OCR text and extracted answer per question |
| `evaluation_results` | per-question scores, rubric breakdown, total, confidence, prompt hash |
| `jobs` | stage and progress of upload/evaluate jobs |
| `data/previews/{sheet_id}/` | `pageN.png`, `regions.json` |

## Failure modes
- **"No answer regions detected" (422)**: the page is blank, rotated badly, or the layout asks for more strips than exist →
  check the preview, pass an explicit `regions_per_page`.
- **Region/key count mismatch** (warning in the log): layout and key disagree → fix the preset in `exam_layouts.py` **and**
  `frontend/src/lib/examLayouts.js`.
- **Empty OCR text, `all_tiers_failed`**: no engine configured or installed → set Vision credentials or install an `ocr_*` extra.
- **Vision `ACCOUNT_STATE_INVALID`**: the key belongs to a Gemini-only project → use a project with the Vision API enabled.
- **Scores look like similarity percentages**: the LLM is off or both providers failed; the result's model label is
  `fallback-legacy` → check `GRADE_ENABLE_LLM` and keys, then `/api/integrations`.
- **Stale grade after editing a key's text, the prompt or a provider setting**: the cache ignores those (it checks only key
  count, layout and the `segmentation_v3` flag) → evaluate with `force_regrade: true`.
