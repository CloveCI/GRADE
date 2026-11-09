# 0003: The schema lives in `db.py` and is mirrored in Supabase migrations

- **Status:** Accepted (records existing behaviour)
- **Date:** 2026-11-08

## Context
GRADE runs against local Docker Postgres in development and Supabase when shared. `db.py` holds idempotent `CREATE ... IF NOT
EXISTS` / `ALTER ... ADD COLUMN IF NOT EXISTS` statements (`init_db`), and `backend/supabase/migrations/` holds timestamped SQL.

## Decision
`db.py` is the source of truth. Migrations are a convenience for Supabase and are kept in step by hand.

## Consequences
- The two drift: `jobs`, `sheet_question_answers` and `sheets.question_regions` exist only in `db.py`. A Supabase database built
  from migrations alone is missing them until `init_db()` runs against it.
- The API calls `init_db()` at startup **only when the core tables already exist** (`api.lifespan`). A fresh, empty database
  needs one explicit `init_db()` call (see [setup](../../getting-started/setup.md)); CI does this before the tests.
- A schema change goes into `db.py` and a new timestamped migration in the same PR.
