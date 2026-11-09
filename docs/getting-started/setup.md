# Setup

> **Audience:** new developers · **Scope:** from a fresh clone to a running API, portal and test suite · **Last verified:** 2026-11-09

## Prerequisites
- Python 3.10+ (developed on 3.12)
- Node.js 20.19+ or 22.12+ and npm (Vite 8 requires it; the portal uses React 19)
- Docker Desktop for the local Postgres 16 + pgvector database, or any PostgreSQL 16+ with the `vector` extension
- PaddleOCR (`ocr_paddle` extra) to find answer positions automatically; without it you must enter a layout per exam.
  The first run downloads its models (a few hundred MB) to `~/.paddlex`.
- For rubric grading, an OpenRouter or Gemini API key. OpenRouter alone is enough (validated with a free-tier key and
  `google/gemini-2.5-flash-lite`).
- Optional: a Google Cloud service account with the Vision API enabled, for better handwriting OCR than local PaddleOCR.

## Clone and enable hooks
```bash
git clone https://github.com/Afeef-crypto/GRADE.git && cd GRADE
sh scripts/setup-hooks.sh
```

## Run each component
### Database
```bash
cd backend
docker compose up -d          # Postgres on host port 5433 (avoids a local 5432)
docker compose ps             # wait for "healthy"
```
**Create the schema once on a fresh database.** The API only re-applies the schema at startup when the core tables already
exist, so an empty database needs one manual call after you create `backend/.env` below (importing `autograder.api` loads it;
`autograder.db` alone does not). On Supabase, applying `backend/supabase/migrations/` is not enough on its own: some tables
exist only in `db.py`, so run this once there too:
```bash
cd backend
PYTHONPATH=src python -c "import autograder.api; from autograder.db import init_db; init_db()"
```

### Backend (FastAPI)
```bash
cd backend
pip install -e ".[api,dev,ocr_paddle]"   # add ocr_google (Vision), llm_gemini, embeddings as needed
cp .env.example .env                     # set GRADE_DATABASE_URL, GRADE_ENABLE_LLM=true and GRADE_OPENROUTER_API_KEY (or Gemini)
PYTHONPATH=src python -m uvicorn autograder.api:app --host 127.0.0.1 --port 8000
```
On Windows PowerShell: `$env:PYTHONPATH = "src"` then the same `uvicorn` line, or `.\scripts\run_api_windows.ps1`.
Environment: `backend/.env.example` documents every variable; the API loads `backend/.env`. Check wiring at
`http://127.0.0.1:8000/api/integrations` (the `llm` block shows whether the key was loaded; restart the API after editing
`.env`).

### Grade a sample
Upload `backend/cie/keys/DISM.docx` with `backend/cie/sheets/DISASTER MITIGATION.pdf` on the Processing page, leave the layout
empty, and grade it. Expect about 2-3 minutes on a CPU, `layout:auto` in the flags, and six regions matching the six answers.
What a good result looks like is in [`../operations/validation.md`](../operations/validation.md).

### Frontend (React + Vite)
```bash
cd frontend
npm ci
npm run dev                              # http://127.0.0.1:5173
```
Leave `VITE_API_URL` empty in development: Vite proxies the API routes to port 8000 (`frontend/vite.config.js`).

## Run the tests
```bash
cd backend && python -m pytest           # needs the database above; set GRADE_TEST_DATABASE_URL to use another one
cd frontend && npm run lint && npm run build
```
OCR and LLM calls are mocked in the tests; only Postgres is real.

## Make a first change
Branch from `staging`, open the PR against `staging`; see [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).
