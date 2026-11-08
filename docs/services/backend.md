# backend

> **Audience:** developers working in `backend/` · **Scope:** what the API does, startup, configuration, run, tests ·
> **Last verified:** 2026-11-08 (`api.py`, `db.py`, `jobs.py`, `pyproject.toml`, `tests/conftest.py`)

**Runs as** a local `uvicorn autograder.api:app` process on `127.0.0.1:8000`; there is no Dockerfile or hosted deploy. It owns
answer keys, sheets, grading and reports, and is the only component that talks to Postgres, OCR and LLM providers.

## What it does
| Area | Routes | Page |
|---|---|---|
| Health and wiring | `GET /health`, `/api/integrations`, `/api/database/status` | this page |
| Keys and sheets | `/upload/key`, `/upload/key/file`, `/upload/exam-bundle`, `/upload/sheet`, `/api/exams*`, `/api/sheets`, `/sheet/{id}/file` | [grading pipeline](../features/grading-pipeline.md) |
| Grading | `/evaluate`, `/result/{id}`, `/result/{id}/rubric`, `PATCH /result/{id}/questions/{region_index}` | [grading pipeline](../features/grading-pipeline.md) |
| Background jobs | `POST /jobs/upload-exam-bundle`, `/jobs/upload-sheet`, `/jobs/evaluate`, `GET /jobs/{id}` | [grading pipeline](../features/grading-pipeline.md) |
| Retrieval debugging | `/api/rag/search`, `/api/sheet/{id}/chunks`, `/api/exam/{id}/key-chunks` | [grading pipeline](../features/grading-pipeline.md) |
| Previews and reports | `/api/sheet/{id}/preview`, `.../preview/page/{n}.png`, `/report/{id}/pdf` | this page |

## Startup
1. Importing `autograder.api` loads `backend/.env` (then the working directory's `.env`) with `interpolate=False`, so `$` in
   passwords survives.
2. `lifespan` calls `database_status()`. If Postgres is reachable **and** the core tables exist, it runs `init_db()` to add
   any missing tables/columns. If the database is unreachable or empty, the API still starts, `/health` reports `degraded`,
   and data routes return 503.
3. `data/uploads` is created relative to the working directory.

## Configuration
Environment variables only; `backend/.env.example` documents each one. The ones that matter most:
`GRADE_DATABASE_URL` (required), `GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_CLOUD_VISION_API_KEY` (OCR),
`GRADE_ENABLE_LLM` + `GRADE_GEMINI_API_KEY` / `GRADE_OPENROUTER_API_KEY` (scoring), `GRADE_CORS_ORIGINS`,
`GRADE_EMBED_BACKEND` (`minilm` is used automatically when `sentence-transformers` is installed; `hash` forces deterministic
vectors), `GRADE_RAG_SIM_THRESHOLD` / `GRADE_RAG_SIM_TEMPERATURE` (retrieval filtering). Optional dependency groups in `pyproject.toml`: `api`, `dev`,
`ocr_google`, `ocr_azure`, `ocr_paddle`, `ocr_trocr`, `llm_gemini`, `embeddings`, `all`.

## Run
`cd backend && PYTHONPATH=src python -m uvicorn autograder.api:app --host 127.0.0.1 --port 8000`
(Windows: `.\scripts\run_api_windows.ps1`). See [setup](../getting-started/setup.md).

## Tests
`cd backend && python -m pytest`. `tests/conftest.py` points `GRADE_DATABASE_URL` at `GRADE_TEST_DATABASE_URL` or the Docker
default `postgresql://grade:grade@127.0.0.1:5433/grade_test`. OCR engines and LLM providers are mocked; Postgres is real, so
API and RAG tests fail with `OperationalError` or 503 when it is not running.

## Gotchas
- **Fresh database:** startup does not create the schema on an empty database; run `init_db()` once
  ([ADR 0003](../architecture/decisions/0003-schema-in-init-db-and-migrations.md)).
- **Run from `backend/`:** uploads are written relative to the working directory, previews relative to the package
  ([ADR 0002](../architecture/decisions/0002-backend-folder-is-the-python-root.md)).
- **Port 5433 already in use:** another Postgres on 5433 gives `password authentication failed for user "grade"`.
- **Jobs are in-process threads:** restarting the API abandons running jobs; their rows stay `running`.
- **No auth:** bind to `127.0.0.1`; do not expose the API publicly.
- **Changing the embedding backend** (installing or removing `sentence-transformers`) leaves vectors from the old backend in
  `answer_key_chunks` / `rag_chunks`; re-upload keys and re-ingest sheets, or similarity scores stop meaning anything.
