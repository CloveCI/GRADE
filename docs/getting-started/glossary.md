# Glossary

> **Audience:** new developers · **Scope:** the words used in GRADE's docs, code and results, in plain language, with where
> each one lives in the code · **Last verified:** 2026-11-09

Terms are grouped by the step where you meet them; the steps are explained in
[`../architecture/overview.md`](../architecture/overview.md).

## Inputs
| Term | Meaning | Where |
|---|---|---|
| **Exam / `exam_id`** | One exam paper. Its key and its students' sheets share the same id (e.g. `cie-dism`) | `answer_keys.exam_id`, `sheets.exam_id` |
| **Answer key / marking scheme** | The model answer and maximum marks for each question | `answer_keys`; read by `key_docx.py`, `key_pdf.py` |
| **Structured key** | A PDF key laid out as question number, question text, marks, then `Answer:`. GRADE reads its sub-parts and sections | `key_pdf._parse_answer_anchored_key` |
| **Choice section** | A part of the paper where only the best *n* answers count ("PART B: answer any 2 of 3") | `answer_keys.section`, `section_pick`; `totals.py` |
| **Sheet** | One student's scanned answer script (PDF or image) | `sheets`; files in `backend/data/uploads/` |
| **Exam bundle** | A key and a sheet uploaded together | `POST /jobs/upload-exam-bundle` |

## Finding the answers
| Term | Meaning | Where |
|---|---|---|
| **Layout / `regions_per_page`** | How many answers are on each page, e.g. `3,1,2`, when the teacher types it | `EvaluateRequest.regions_per_page` |
| **Automatic layout** | GRADE finds each answer itself from the page text, the margin labels and the model answers; results carry the flag `layout:auto` | `answer_layout.py` |
| **Margin label** | What a student writes in the left margin to start an answer ("1st Ans", "2nd Ans"); used as a hint for where answers begin | `answer_layout.margin_label_spans` |
| **Preset** | A fixed layout stored per exam; now used only when automatic layout cannot run | `exam_layouts.py` |
| **Region / question region** | The part of the sheet that holds one answer; it can span pages | `sheets.question_regions` |
| **Strip** | One page's piece of a region (an answer on two pages has two strips) | `preprocessing.py` |
| **Preview** | Page images with a box drawn around each region, shown in the portal | `sheet_preview.py`, `backend/data/previews/` |

## Reading and searching
| Term | Meaning | Where |
|---|---|---|
| **OCR** | Turning handwriting into text. Engines are tried in order until one works: Google Vision, Azure, PaddleOCR, TrOCR | `ocr.py` |
| **OCR confidence** | How sure the OCR engine was (0-1); below 0.6 the result is flagged for review | `QuestionResult.ocr_confidence` |
| **OCR clean-up** | Fixing obvious OCR mistakes before marking. An optional LLM pass never sees the model answer; a rewrite in the key's words is rejected (`ocr_llm_rejected_key_drift`) | `text_format.py` |
| **Search index / chunk** | Small pieces of the key and of the student's text, stored with a vector (embedding) so similar text can be found | `rag_chunks` |
| **Hybrid search** | Finding pieces by meaning (vectors) and by words (full-text search) at once, combining both rankings | `db.hybrid_search_rag_chunks` |

## Marking
| Term | Meaning | Where |
|---|---|---|
| **Pairing by order** | Answer *n* is marked against question *n* | `evaluation_service.run_evaluation` |
| **KEY SIDE / STUDENT SIDE** | The two halves of what the LLM is shown: the model answer with its key pieces, and the student's answer with its pieces | `rag/retrieval.format_grading_context` |
| **Rubric** | The four things marked, each 0-4: factual accuracy, conceptual completeness, reasoning, domain terminology | `prompts/grading_v2.txt`, `scoring.py` |
| **Grader label / `llm_model`** | Which grader produced the marks, e.g. `openrouter:google/gemini-2.5-flash-lite`; `mixed: ...` if it changed mid-sheet | `evaluation_results.llm_model` |
| **`fallback-legacy`** | Marks from a simple text-similarity score, used when no LLM worked; the feedback says why | `scoring._legacy_fallback_score` |
| **Grading confidence** | How sure the grader was overall (high / medium / low) | `scoring.aggregate_grading_confidence` |

## Results
| Term | Meaning | Where |
|---|---|---|
| **Evaluation result** | The stored grade for one sheet: every question's marks, feedback and flags, and the total | `evaluation_results`, `GET /result/{id}` |
| **Counted** | Whether an answer counts towards the total; `false` for the dropped answer in a choice section | `QuestionResult.counted` |
| **`region_missing`** | No answer region was found for this question, so it got 0 marks; enter the layout and re-grade | `evaluation_service.run_evaluation` |
| **`review_required`** | The result needs a teacher's look (low confidence, empty OCR, fallback marks...) | result and question flags |
| **Teacher correction (HITL patch)** | Changing one question's marks or feedback by hand; the total is recalculated. HITL = human in the loop | `PATCH /result/{id}/questions/{n}` |
| **Job** | A background upload or grading run; the portal polls its progress | `jobs`, `GET /jobs/{id}` |

## Code-only terms
| Term | Meaning | Where |
|---|---|---|
| **Corpus / document id** | The groups inside the search index: `keys_{exam_id}` and `sheet_{sheet_id}` | `rag/ingest.py` |
| **Patch** | The image of a region handed to OCR | `PreprocessResult.patches` |
| **Boundary helpers** | Older code that trims text bleeding in from a neighbouring answer; not used when grading | `rag/boundaries.py` |
