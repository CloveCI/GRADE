# Glossary

> **Audience:** new developers · **Scope:** the project's vocabulary, with where each term lives in the code ·
> **Last verified:** 2026-11-08

Where the code uses a different word from the product, both are listed.

| Term | Meaning | Where |
|---|---|---|
| **Exam / `exam_id`** | One exam paper; keys and sheets are grouped by it (e.g. `cie-daa`, `cie-dm`) | `sheets.exam_id`, `answer_keys.exam_id` |
| **Answer key / marking scheme** | The model answer and max marks for each question | `answer_keys` table; parsed by `key_docx.py`, `key_pdf.py` |
| **Sheet** | One student's uploaded answer script (PDF or image) | `sheets` table; file in `backend/data/uploads/` |
| **Exam bundle** | Key + sheet uploaded together in one request | `POST /upload/exam-bundle`, `POST /jobs/upload-exam-bundle` |
| **Strip / raw region** | A horizontal band of one page that holds (part of) an answer | `preprocessing.py` |
| **Layout / `regions_per_page`** | Comma-separated strips per PDF page, e.g. `3,1,2,1` | `exam_layouts.py`, mirrored in `frontend/src/lib/examLayouts.js` |
| **Merge groups** | Which raw strips form one question (Q4 spanning pages 2-3 in `cie-daa`) | `exam_layouts.py` |
| **Question region** | The merged strips for one question, with page span | `sheets.question_regions` (JSONB column) |
| **Patch** | The preprocessed image of a region that is sent to OCR | `preprocess_sheet_for_evaluation()` → `pp.patches` |
| **OCR tier** | One engine in the fallback chain: Google Vision → Azure → PaddleOCR → TrOCR | `ocr.py` (`ocr_patch`) |
| **Chunk** | A slice of key or sheet text stored with an embedding for retrieval | `rag_chunks`, `answer_key_chunks` |
| **Hybrid retrieval** | Vector similarity (pgvector) combined with Postgres full-text search | `rag/retrieval.py` |
| **Boundary trim** | Cutting OCR text that bled in from the neighbouring answer | `rag/boundaries.py` |
| **Rubric** | The scoring dimensions and JSON output the LLM must follow | `prompts/grading_v2.txt`, `scoring.py` |
| **Legacy fallback** | Cosine-similarity score used when the LLM is off or fails | `scoring._legacy_fallback_score` |
| **Grading confidence** | Aggregate of OCR and LLM confidence for a result | `scoring.aggregate_grading_confidence` |
| **Evaluation result** | The stored grade for one sheet, per question and in total | `evaluation_results` table, `GET /result/{id}` |
| **HITL patch** | A teacher's manual correction to one question's score | `PATCH /result/{id}/questions/{region_index}` |
| **Job** | A background upload or evaluate run with stage and progress | `jobs` table, `jobs.py`, `GET /jobs/{id}` |
| **Deferred ingest** | Sheet OCR/RAG is skipped at upload and done at evaluate | `sheet_ingest` in upload responses, `api.py` |
| **Preview** | Rendered page PNGs plus `regions.json` overlays for the evaluator UI | `sheet_preview.py`, `backend/data/previews/{sheet_id}/` |
