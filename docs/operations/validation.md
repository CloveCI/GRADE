# Validation: what has been tested, and how far to trust a grade

> **Audience:** teachers and developers deciding whether to rely on a GRADE result · **Scope:** the test runs behind the current
> claims, their results, what was not tested, input requirements and known limits · **Last verified:** 2026-11-09

**Short answer:** given a CIE-style answer booklet and a marking scheme for the same paper, GRADE finds the answers, reads them
and produces a sensible grade, but it has been checked in full on **one** sheet. Treat every result as a first-pass grade that
a teacher reviews, not as a final mark.

## Test environment (2026-11-09)
| Part | Used |
|---|---|
| Machine | Windows 11, Python 3.12, CPU only |
| Database | throwaway `pgvector/pgvector:pg16` container (same image as `backend/docker-compose.yml`) |
| OCR | local PaddleOCR 3.3.2; **Google Vision not configured** |
| Embeddings | MiniLM (`sentence-transformers` installed) |
| LLM | OpenRouter `google/gemini-2.5-flash-lite` (free-tier key) |
| Route | the portal's API routes: `POST /jobs/upload-exam-bundle` with **no layout**, then `POST /jobs/evaluate` |
| Automated tests | `python -m pytest`: 182 passed against the real database |

## Results
**Answer keys**

| Key | Questions found | Marks | Paper maximum |
|---|---|---|---|
| Reformatted Disaster Mitigation key (PDF) | Q1-Q6 (4a/4b and 6a/6b merged) | 2, 2, 2, 7, 7, 7 | 20 (Part B: best 2 of 3) |
| `backend/cie/keys/DISM.docx` | Q1-Q6 | 2, 2, 2, 7, 7, 7 | 27 (the DOCX has no PART lines, so no choice rule) |

**Where each answer is** (automatic layout, no layout entered)

| Sheet | Boundaries right | Notes |
|---|---|---|
| Disaster Mitigation (3 pages) | 6 of 6 | margin labels found for all 6 answers |
| Data Mining (5 pages) | 6 of 6 | Q2 and Q4 run across pages |
| DAA (5 pages) | 5 of 6 | one sentence from the end of Q1 graded with Q2; the old `cie-daa` preset covered only 4 of 5 pages and never graded Q6 |

**Full grading** (Disaster Mitigation sheet only)

| Key | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Total |
|---|---|---|---|---|---|---|---|
| PDF key | 1.5/2 | 2/2 | 1.5/2 | 6/7 | 5.75/7 | 5/7 (not counted) | **16.8 / 20** |
| DOCX key | 2/2 | 2/2 | 1.5/2 | 7/7 | 6/7 | 7/7 | 25.5 / 27 |

- OCR confidence 0.70-0.77 per answer: readable but noisy ("A hagard is a danger..is ewint or Condition").
- Retrieval: the sheet was indexed with 14 chunks; each question's context held only its own key excerpts.
- The OCR clean-up tried once to rewrite an answer in the key's wording; the guard rejected it and graded the raw text.
- Evaluation took about 140 s for 3 pages on CPU; finding the answer positions adds about 60 s of that.

## Not tested
Google Vision, Gemini called directly, Azure, image (non-PDF) sheets, scanned key PDFs, full grading of any sheet other than
Disaster Mitigation, the portal used by hand (only its API routes), and agreement with a human examiner.

## It is expected to work when
- answers are written **in question order**, with a label such as "1st Ans" / "2nd Ans" in the ruled left margin;
- every question is answered, or any skipped questions are at the end;
- the key is DOCX, JSON, or a text PDF laid out as question number, question text, marks, then `Answer:`
  (a plain numbered list also works, less robustly);
- PaddleOCR is installed (automatic layout needs it) and an LLM key is set (OpenRouter or Gemini) for rubric grading.

## Known limits
| Limit | Effect | Workaround |
|---|---|---|
| Answers are paired with questions **by position** | a skipped or out-of-order answer is graded against the wrong question | review in the evaluator; no automatic fix yet (see the last section) |
| Choice papers rely on order too | "best 2 of 3" is right only when skipped questions come last | review choice sections by hand |
| Local OCR is noisy | the LLM grades through misspellings | configure Google Vision |
| Boundaries can slip by a line | seen once in 18 boundaries (DAA) | look at the region boxes; enter the layout and re-grade |
| Grades depend on how detailed the key is | the same sheet scored 16.8/20 against the detailed PDF key and 25.5/27 against the short DOCX key | use full model answers |
| DOCX keys do not carry PART choice rules | totals count every question | use a structured PDF or JSON key with `section` / `section_pick` |
| Accuracy is unmeasured | no agreement figure against human examiners | treat grades as provisional |

## Before trusting a grade
1. Open the sheet in the evaluator and check that each question's box covers that answer and nothing else.
2. Re-check anything flagged `review_required`, `region_missing`, `ocr_empty` or with low confidence.
3. Check the grader label: `fallback-legacy` means no LLM graded it (the feedback names the failing provider).
4. On choice papers, confirm the answer marked not counted is the one the student would expect.
5. Correct a score in place when needed; the total is recalculated with the same choice rule.

## Reproducing the run
Start the database and API as in [setup](../getting-started/setup.md) with PaddleOCR installed and an LLM key in
`backend/.env`, then upload a key and a sheet with **no layout** (portal: Processing page, layout field left empty; API:
`POST /jobs/upload-exam-bundle`), evaluate with `force_regrade: true`, and compare the result's regions, flags
(`layout:auto`, `section_choice:...`) and marks with the tables above. The sample sheets are in `backend/cie/sheets/`.

## What would make it dependable
1. Pair answers with questions by the label the student wrote ("5th Ans"), not by position.
2. Repeat this validation with Google Vision.
3. Grade a few dozen sheets alongside a human examiner and record the agreement here.

Next: [`../features/grading-pipeline.md`](../features/grading-pipeline.md) · [`runbook.md`](runbook.md)
