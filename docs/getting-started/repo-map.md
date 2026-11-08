# Repository map

> **Audience:** new developers · **Scope:** what lives where, and what is deployed · **Last verified:** 2026-11-08

Nothing is deployed automatically: GRADE runs as a local FastAPI process, a Vite dev server (or a static build) and a Postgres
database. Everything else here is code, tests, or tooling.

## Top level

| Path | What it is | Deployed as |
|---|---|---|
| [`backend/`](../../backend) | FastAPI API and the `autograder` package, its tests, scripts, migrations and sample data | local `uvicorn` process on port 8000 |
| [`frontend/`](../../frontend) | GRADE Companion, the React 19 + Vite portal | Vite dev server on 5173, or static `dist/` |
| [`scripts/`](../../scripts) | Repository checks run by CI (`scripts/ci/`) and git hooks | not deployed |
| [`docs/`](..) | This documentation | not deployed |
| [`.github/`](../../.github) | Workflows, Dependabot, templates, CODEOWNERS, rulesets | GitHub |
| [`scripts/githooks/`](../../scripts/githooks) | Local git hooks (enable with `scripts/setup-hooks.sh`) | developer machines |

The root holds only `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, and the dotfiles git and editors require.
Personal tool folders (`.claude/`, `.vscode/`, `.cursor/`) are deliberately not tracked, so every developer can have their own.

## backend

```
backend/
  src/autograder/
    api.py               FastAPI app: every HTTP route, startup (lifespan), CORS
    jobs.py              background threads for upload and evaluate jobs (polled via GET /jobs/{id})
    evaluation_service.py  the evaluate pipeline: segment, OCR, retrieve, score, persist
    preprocessing.py     OpenCV: PDF render, deskew, strip segmentation, multi-page merge
    exam_layouts.py      per-exam strips-per-page presets and aliases
    ocr.py               tiered OCR: Google Vision, Azure, PaddleOCR, TrOCR
    scoring.py           rubric scoring: mock, Gemini, OpenRouter, legacy cosine fallback
    llm_providers.py     provider keys, model names, prompt builders
    prompts/             grading_v2.txt, ocr_format_v1.txt
    rag/                 ingest, retrieval (pgvector + FTS), answer-boundary trimming, similarity
    embeddings.py        128-D local hash embeddings, optional Sentence-Transformers
    db.py                Postgres access and the idempotent schema (init_db)
    key_docx.py, key_pdf.py, key_chunks.py   answer-key parsing and chunking
    report_pdf.py        ReportLab PDF report
    sheet_preview.py     page PNGs and regions.json for the evaluator UI
    schemas.py           Pydantic request/response models
  tests/                 pytest suite (Postgres real, OCR/LLM mocked)
  scripts/               verify_*.py, OCR/RAG utilities, Windows launchers; run from backend/
  supabase/migrations/   timestamped SQL for Supabase (init_db mirrors it)
  cie/keys, cie/sheets   sample marking schemes (.docx) and scanned sheets (.pdf)
  data/                  runtime output, gitignored: uploads/ and previews/{sheet_id}/
  docker-compose.yml     local Postgres 16 + pgvector
```

## frontend

```
frontend/
  src/pages/             one component per route (Upload, Evaluator, Dashboard, Reports, Inspect, Settings, Docs, ...)
  src/components/        AppShell, Sidebar, Topbar, Footer
  src/lib/               api.js (fetch wrapper), jobs.js (job polling), examLayouts.js (mirror of exam_layouts.py)
  src/hooks/             useApiStatus
  vite.config.js         dev proxy to the API
```

## What is not here any more
- `frontend-react/` became `frontend/`; the old `frontend/` was an npm shim that delegated to it.
- `src/`, `tests/`, `scripts/*.py`, `supabase/`, `cie/`, `pyproject.toml` and `docker-compose.yml` moved under `backend/`.
  The last commit with the old layout is `3eb533c` on `main`.

## Next

[`glossary.md`](glossary.md) · [`../architecture/overview.md`](../architecture/overview.md)
