# 0004: Answer positions come from the marking scheme, not per-exam layout presets

- **Status:** Accepted
- **Date:** 2026-11-09

## Context
Each sheet must be cut into one region per answer-key question. Without a layout, a multi-page sheet became one region per
page (3 regions for the 6-question Disaster Mitigation sheet, so Q4-Q6 were never graded). Presets did not fix it: `cie-daa`
(`3,1,2,1`) covers 4 of the DAA sample's 5 pages, so Q6 was never graded; the portal pre-filled `3,1,2,1` for any
6-question exam; and equal-split strips cut answers mid-way (Q6's first line graded inside Q5).

## Decision
- Without a layout entered by the teacher, `answer_layout.py` finds the regions: page OCR lines (PaddleOCR), handwritten
  answer labels in the ruled margin, and a dynamic-programming split of the lines by similarity to each model answer.
- Precedence in evaluate: teacher's layout → automatic layout (`layout:auto`) → preset only when automatic layout cannot run.
- The portal no longer pre-fills or forces presets.

## Consequences
- Evaluate takes longer (each page is OCRed once more to find lines: about 140 s instead of 77 s for 3 pages locally).
- Automatic layout needs PaddleOCR even when Google Vision does the reading; without it, presets or `region_missing` apply.
- Measured on three CIE samples: 17 of 18 boundaries right (DAA moved one sentence between Q1 and Q2). A teacher can always
  enter the layout to override it.
