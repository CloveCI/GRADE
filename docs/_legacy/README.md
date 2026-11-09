# Legacy material

Older documents kept as **source material** for the maintained pages under `docs/`. They are **not maintained and may be wrong**.

Rules:
- Do not link to these from new pages except as "source".
- When you write a maintained page from one of them, verify each claim against the code, then delete the legacy file in the same PR.
- Anything not worth migrating gets deleted; git history keeps it.

| File | What it is | Status |
|---|---|---|
| `ARCHITECTURE.md` | v1 system design (Sentence-BERT scoring diagram, 3-tier OCR) | Partly migrated into `architecture/overview.md`; scoring section is out of date |
| `IMPLEMENTATION_PLAN.md` | v2 phased plan, rubric prompt spec, test metrics | Not yet migrated; rubric spec belongs in a future `features/rubric-scoring.md` |
| `DESIGN-fairlens.md` | Design tokens for an unrelated project (FairLens) found at the old repo root | Not GRADE; delete unless someone claims it |
| `requirements.txt` | Old pip list, superseded by `backend/pyproject.toml` extras | Superseded; delete once nobody installs from it |
