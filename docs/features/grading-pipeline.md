# Grading pipeline

> **Audience:** developers changing how sheets are segmented, read or scored · **Scope:** what happens from upload to report,
> status, data, failure modes · **Last verified:** 2026-11-08 (`api.py`, `jobs.py`, `evaluation_service.py`, `scoring.py`, `ocr.py`)

## Status
Works end to end on the bundled CIE samples (`backend/cie/`) with Google Vision and Gemini configured. Without credentials it
still runs: OCR falls through to whatever local engines are installed, and scoring uses the cosine-similarity fallback, which is
only a rough signal. Agreement with human examiners has not been measured. Retrieval does less than the code's docstrings
suggest; see [Known gaps in retrieval](#known-gaps-in-retrieval).

## How it works
1. **Key upload.** DOCX, JSON or text PDF is parsed into one row per question with model answer and max marks
   (`key_docx.py`, `key_pdf.py`), then chunked and embedded for retrieval (`key_chunks.py`, `rag/ingest.py`).
2. **Sheet upload.** The file is saved to `data/uploads/sheet_*.pdf` and a `sheets` row is created. The portal's job routes
   skip OCR and indexing (`sheet_ingest: deferred`). The sync routes `/upload/sheet` and `/upload/exam-bundle` instead run
   `ingest_sheet_rag()` straight away: OCR, chunk, embed into `rag_chunks` as `sheet_{sheet_id}`.
3. **Cache check.** `run_evaluation()` returns the latest stored result for the sheet and exam (`existing_evaluate_response`)
   unless `force_regrade` is set, the number of keys changed, the resolved layout differs (`layout:` flag), or the result
   predates `segmentation_v3`.
4. **Layout.** `resolve_regions_per_page()` takes the request's layout, else the exam preset, else infers from the key count
   (`exam_layouts.py`). Example: `cie-daa` = `3,1,2,1`, with Q4 merged from strips on pages 2 and 3.
5. **Segment.** `preprocess_sheet_for_evaluation()` renders pages at `GRADE_PDF_RENDER_SCALE` (default 3.0), deskews, finds
   ink-aware strip boundaries, and merges strips into question regions. Regions are stored in `sheets.question_regions`
   and rendered as previews (`sheet_preview.py`).
6. **Pair and OCR.** Patch *n* is graded against key *n* (`keys[idx]`); `match_answer_key()` is not used by evaluate.
   `ocr_patch()` tiles very tall patches, then tries Google Vision (`DOCUMENT_TEXT_DETECTION`), Azure, PaddleOCR, TrOCR
   in order, returning text, confidence and the engine used. `GRADE_OCR_GOOGLE_ONLY` / `GRADE_OCR_CLOUD_ONLY` narrow the chain.
7. **Merge indexed sheet text.** `retrieve_sheet_answer_for_question()` loads any `sheet_{sheet_id}` chunks tagged with the
   question and slices the fresh OCR by their stored offsets; if that text is longer it replaces the OCR, otherwise it is
   appended when not already contained. With no indexed chunks this step does nothing.
8. **Retrieve context.** `retrieve_context_for_grading()` runs hybrid search on `keys_{exam_id}` (query: question id + model
   answer) and lists the sheet chunks for the question, then formats a KEY SIDE / STUDENT SIDE block. The model answer,
   the student's OCR and the instructions are always included in full; `max_chars` (3,200) budgets only the retrieved
   excerpts, which are dropped first when the essentials are long. That block is the only place the student's answer
   appears in the LLM prompt.
9. **Score.** `score_answer_llm()`: if `GRADE_ENABLE_LLM` is off → legacy cosine score; else `GRADE_LLM_MOCK_RESPONSE` (tests) →
   Gemini → OpenRouter → legacy. The prompt is `prompts/grading_v2.txt`; the output is rubric JSON with marks, feedback and
   confidence.
10. **Persist.** Per-question answers go to `sheet_question_answers`; the whole result, with prompt hash and model label, goes to
   `evaluation_results`.
11. **Review.** The evaluator page shows each region over its page image; a teacher can patch a question's marks and feedback.
12. **Report.** `GET /report/{id}/pdf` builds the ReportLab PDF.

## Data
| Table / path | What it holds |
|---|---|
| `answer_keys` | question id, model answer, max marks, sort order, per exam |
| `answer_key_chunks` | per-key model-answer chunks and 128-D vectors (no FTS index; not queried at grading time) |
| `rag_chunks` | the retrieval corpus: `keys_{exam_id}` copied from `answer_key_chunks`, `sheet_{sheet_id}` from sheet ingest; HNSW + FTS indexes |
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
- **STUDENT SIDE says "no additional sheet chunks retrieved"**: the sheet was uploaded through the portal and never indexed →
  `POST /api/sheet/{id}/ingest`, then evaluate with `force_regrade: true`.
- **Stale grade after editing a key's text, the prompt or a provider setting**: the cache ignores those (it checks only key
  count, layout and the `segmentation_v3` flag) → evaluate with `force_regrade: true`.

## Known gaps in retrieval
Found by reading the code on 2026-11-08 and confirmed on the Disaster Mitigation sample (local PaddleOCR, MiniLM). Only #5 is
fixed. The rest are why "Hybrid retrieval" is **Partial** in [`product.md`](../product.md).

| # | Gap | Where | Effect on grading |
|---|---|---|---|
| 1 | Job uploads say `sheet_ingest: deferred, reason: ocr_at_evaluate`, but `run_evaluation()` never calls `ingest_sheet_rag()` | `jobs.py`, `evaluation_service.py` | For every portal upload the `sheet_{sheet_id}` corpus is empty: no STUDENT SIDE excerpts, no `sheet_rag_by_question` flag, empty Inspect page |
| 2 | When a sheet *was* indexed (sync routes, `/api/sheet/{id}/ingest`), the chunks are a snapshot. Ingest reads only `GRADE_OCR_FULL_PAGE` (not render scale, patch size or padding), never uses consensus OCR, and is not refreshed by `force_regrade` or a layout change | `rag/ingest.py` (`_preprocess_options_from_env`) vs `preprocessing.preprocess_options_from_env` | Evaluate merges old chunk text into fresh OCR (step 7) and shows it as STUDENT SIDE, so the LLM can see two different transcripts of the same answer |
| 3 | Full-text half of hybrid search rarely matches during grading: `plainto_tsquery` ANDs every term, and the grading queries add words that never occur in chunks ("reference", "handwritten") plus the whole model answer | `db.search_rag_chunks_bm25`, `retrieval._key_corpus_query`, `_sheet_corpus_query` | Grading retrieval is effectively vector-only. The Inspect page uses short queries, so FTS works there, and what you see is not what grading gets |
| 4 | The fused rank is discarded: hybrid results are re-sorted by cosine similarity and filtered at `GRADE_RAG_SIM_THRESHOLD` | `db.hybrid_search_rag_chunks` → `annotate_hits_with_similarity` | RRF only chooses the candidate set; ordering is pure vector similarity |
| 5 | **Fixed 2026-11-08.** The grading context was cut at `max_chars + 400` (3,600) characters after the full model answer and OCR text were written | `retrieval.format_grading_context` | With the reformatted Disaster Mitigation key (~3.5k-char answers for Q4–Q6) the LLM received no student answer for Q4 and Q6 and 7 characters for Q5, i.e. 21 of 27 marks graded blind. Now only excerpts are budgeted |
| 6 | KEY SIDE excerpts prefer the same `question_id` but do not exclude other questions' key chunks | `retrieval._hits_for_question` | Seen on all 6 Disaster Mitigation questions: e.g. Q2's KEY SIDE also carried Q1 and Q4 excerpts |
| 8 | The similarity cut-off removes correct sheet chunks when OCR is noisy, and full-text matches cannot rescue them because filtering uses cosine similarity only | `rag/similarity.filter_hits_by_threshold` (0.35) | "Bhopal methyl isocyanate gas leak": the right Q6 sheet chunk scores 0.32 and is dropped although FTS matches "Bhopal" |
| 7 | `/api/rag/search` with `exam_id` but no `sheet_id` searches every document, takes the global top *k*, then drops other exams | `api.api_rag_search` | The Inspect page can show fewer than *k* results, or none, for an exam that has matches |

Suggested order for the rest: 1 (ingest at the start of evaluate, using the evaluate preprocessing options, which also
fixes 2), then 3, 6 and 8 (build FTS queries from keywords with `OR`; filter key hits to the question; let an FTS match
survive the cosine cut-off), then 7.

Positional pairing is the right choice for now: on the same sample, retrieving a key from the student's own words picked
the wrong question for Q4 (→ Q2) and Q5 (→ Q1), so `match_answer_key()` should stay out of evaluate until OCR improves.
