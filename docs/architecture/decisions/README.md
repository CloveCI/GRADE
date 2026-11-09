# Architecture decisions

> **Audience:** developers changing the architecture · **Scope:** short records of decisions that are easy to undo by
> accident · **Last verified:** 2026-11-09

Each record says what was decided, why, and what it costs. Add one when a decision would otherwise be re-argued, or when
undoing it would cause an incident. Keep them short. Numbering is chronological and never reused.

| # | Decision | Status |
|---|---|---|
| [0001](0001-staging-branch-and-protected-main.md) | `staging` is the integration branch; `main` is protected and promotion-only | Accepted, 2026-11-08 |
| [0002](0002-backend-folder-is-the-python-root.md) | `backend/` is the Python project root; `.env`, `data/` and `cie/` resolve relative to it | Accepted, 2026-11-08 |
| [0003](0003-schema-in-init-db-and-migrations.md) | The schema lives in `db.py` (`init_db`) and is mirrored in Supabase migrations | Accepted, 2026-11-08 |
| [0004](0004-automatic-answer-layout-over-presets.md) | Answer positions come from the marking scheme, not per-exam layout presets | Accepted, 2026-11-09 |

Template:

```markdown
# NNNN: Title
- **Status:** Proposed | Accepted | Superseded by NNNN
- **Date:** YYYY-MM-DD
## Context
## Decision
## Consequences
```
