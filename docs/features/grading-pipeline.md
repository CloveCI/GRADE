# Grading pipeline

> **Audience:** developers changing how sheets are segmented, read or scored · **Scope:** what happens from upload to report,
> status, data, failure modes · **Last verified:** 2026-11-09 (`key_pdf.py`, `answer_layout.py`, `evaluation_service.py`,
> `rag/`, `text_format.py`, `scoring.py`, `totals.py`; end-to-end run on the Disaster Mitigation sample with PaddleOCR and OpenRouter)

## Status
Works end to end on the bundled CIE samples (`backend/cie/`). Verified on 2026-11-09 with local PaddleOCR (no Google Vision)
and OpenRouter `google/gemini-2.5-flash-lite`, with **no layout entered**: the reformatted Disaster Mitigation key parsed into
6 questions (2/2/2/7/7/7, Part B best 2 of 3), automatic layout found all 6 answers, and the sheet scored 16.8 / 20.
Without credentials it still runs: OCR uses whatever local engines are installed and scoring falls back to cosine
similarity, which is only a rough signal. Agreement with human examiners has not been measured.

## How it works
1. **Key upload.** DOCX, JSON or PDF is parsed into one row per question with model answer, max marks and, when the paper
   has a choice, `section` / `section_pick` (`key_docx.py`, `key_pdf.py`). PDF keys that label answers with `Answer:` are
   parsed by question header: the closest `N.` / `a)` line above each label, marks from the Marks/CO/BTL numbers, sub-parts
   merged per question, running headers and the appendix removed, `PART – B (2×7 = 14 Marks)` read as best 2 of 3. Other PDF
   keys are split on numbered lines. Keys are chunked into `answer_key_chunks` and copied into `rag_chunks` as `keys_{exam_id}`.
2. **Sheet upload.** The file is saved to `data/uploads/sheet_*.pdf`. The portal's job routes do no OCR here
   (`sheet_ingest: deferred`); the sync routes `/upload/sheet` and `/upload/exam-bundle` still index immediately.
3. **Cache check.** `run_evaluation()` returns the latest stored result unless `force_regrade` is set, the key count
   changed, the layout differs (`layout:` flag; an automatic-layout result is reused when no layout is requested), or the
   result predates `segmentation_v3`.
4. **Layout.** In order: the layout the teacher entered (`regions_per_page`); otherwise **automatic layout**
   (`answer_layout.py`, flag `layout:auto`); otherwise, only if automatic layout cannot run (PaddleOCR missing), a built-in
   preset from `exam_layouts.py`. Automatic layout OCRs each page into positioned lines, detects handwritten answer labels
   in the ruled margin from the ink, and splits the lines into one contiguous group per key question by dynamic
   programming (character-trigram similarity to each model answer, plus a bonus at labelled lines). Answers may span pages.
5. **Segment.** `preprocess_sheet_for_evaluation()` renders pages at `GRADE_PDF_RENDER_SCALE` (default 3.0), deskews, and
   produces one region per question (several strips when it spans pages). Regions are saved in `sheets.question_regions`;
   the preview draws them (`sheet_preview.py`).
6. **Read.** Every region is OCRed once (`ocr_patch()`: Google Vision, Azure, PaddleOCR 2.x/3.x, TrOCR in order).
7. **Index.** That exact OCR replaces `sheet_{sheet_id}` in `rag_chunks` (`index_sheet_ocr`), so retrieval never serves an
   older transcript.
8. **Clean up.** `format_student_answer()` fixes OCR noise with heuristics and, when an LLM is configured, an LLM pass that
   sees only the question stem and a domain-term list. A pass that adds 3+ key words the student never wrote, or replaces
   over a quarter of the words, is rejected (`ocr_llm_rejected_key_drift` / `ocr_llm_rejected_drift`).
9. **Pair and retrieve.** Region *n* is graded against key *n*. `retrieve_context_for_grading()` takes this question's key
   excerpts (hybrid search: vector + OR-ed full-text, fused by reciprocal rank) and this question's sheet chunks, and
   formats a KEY SIDE / STUDENT SIDE block. The model answer, the student's answer and the instructions are never cut;
   `max_chars` budgets only the excerpts.
10. **Score.** `score_answer_llm()`: Gemini → OpenRouter → cosine fallback. The fallback is labelled `fallback-legacy` and
    flags only the providers that actually failed. The sheet's `llm_model` is the grader every question used, or `mixed: …`.
11. **Total.** `totals.apply_section_choice()` counts the best `section_pick` answers of a choice section; `max_total`
    matches the printed paper. Keys without a region are listed with 0 marks and `region_missing`.
12. **Review and report.** The evaluator page shows each region over its page; a teacher patch recomputes the total with the
    same choice rule. `GET /report/{id}/pdf` builds the ReportLab PDF.

## Data
| Table / path | What it holds |
|---|---|
| `answer_keys` | question id, model answer, max marks, sort order, `section`, `section_pick` |
| `answer_key_chunks` | per-key model-answer chunks and 128-D vectors (copied into `rag_chunks`; not queried directly) |
| `rag_chunks` | retrieval corpus: `keys_{exam_id}` and `sheet_{sheet_id}` (rebuilt by every evaluate); HNSW + FTS indexes |
| `sheets` | file path, exam id, `question_regions` JSONB (`auto: true` when found by automatic layout) |
| `sheet_question_answers` | OCR text and cleaned answer per question |
| `evaluation_results` | per-question scores (with `counted`), rubric breakdown, total, confidence, grader label, flags |
| `jobs` | stage and progress (`ocr_read`, `index_sheet`, `ocr_evaluate`) |
| `data/previews/{sheet_id}/` | `pageN.png`, `regions.json` |

## Failure modes
- **`region_missing` on some questions**: fewer regions than keys (automatic layout could not run and no layout was given)
  → install PaddleOCR (`pip install -e ".[ocr_paddle]"`) or enter the layout, then re-grade.
- **A boundary off by a line or two** (seen once in three samples: DAA Q1/Q2): the answer labels were not detected and two
  answers share vocabulary → enter the layout for that exam.
- **Empty OCR text, `all_tiers_failed`**: no engine configured or installed → set Vision credentials or install an `ocr_*` extra.
- **Scores look like similarity percentages**: grader label `fallback-legacy`; the feedback names the failing provider
  (e.g. OpenRouter 401 = key revoked or unknown) → fix the key, restart the API.
- **`ocr_llm_rejected_key_drift`**: the clean-up tried to rewrite the answer in the key's wording; the heuristic text was
  graded instead. Expected occasionally; frequent rejections mean the clean-up model is unsuitable.
- **Stale grade after editing a key's text, the prompt or a provider setting**: the cache does not check those →
  evaluate with `force_regrade: true`.

## Retrieval: what was fixed and what remains
Found on 2026-11-08 and fixed on 2026-11-09, confirmed on the Disaster Mitigation sample:

| Was | Now |
|---|---|
| Evaluate never indexed the sheet, so STUDENT SIDE was empty after portal uploads; older ingests were merged into fresh OCR | evaluate indexes the OCR it grades; the merge step is gone |
| Full-text search ANDed every word and matched none of the 12 grading queries | terms are OR-ed (`to_tsquery`), sanitised |
| Fused RRF order was re-sorted away by cosine similarity | RRF order kept |
| Other questions' key excerpts appeared under "Question N" | only the graded question's excerpts |
| Correct noisy-OCR chunks fell under the 0.35 cut-off although they matched by keyword | a full-text match survives the cut-off |
| Exam-only search filtered a global top-k | searches that exam's documents |
| The grading context was cut at 3,600 characters, so long answers were graded blind | never cut; excerpts are budgeted |

Still open: positional pairing stays (retrieving a key from the student's own words picked the wrong question for 2 of 6
answers on the sample), and the DOCX parser does not read PART choice sections.
