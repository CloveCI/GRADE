# GRADE backend

FastAPI service and the `autograder` Python package: answer-key parsing, sheet segmentation, tiered OCR, hybrid RAG
over Postgres + pgvector, LLM rubric scoring and PDF reports. The React portal in [`../frontend`](../frontend) talks to it.

```
src/autograder/        the package (api.py is the FastAPI app; rag/ holds retrieval; prompts/ the LLM prompts)
tests/                 pytest suite (needs Postgres + pgvector; external OCR/LLM calls are mocked)
scripts/               verification, OCR and RAG utilities, run from this folder
supabase/migrations/   Postgres schema (the API also runs init_db() on startup)
cie/                   sample answer keys (.docx) and scanned sheets (.pdf)
docker-compose.yml     local Postgres 16 + pgvector on port 5433
.env.example           every environment variable the API reads
```

All commands run **from this folder** (`backend/`). The API loads `backend/.env` and writes uploads and previews to `backend/data/`.

```bash
pip install -e ".[api,dev]"                 # add ocr_google, llm_gemini, embeddings as needed
cp .env.example .env                        # then set GRADE_DATABASE_URL and provider keys
docker compose up -d                        # local Postgres + pgvector
PYTHONPATH=src python -m uvicorn autograder.api:app --host 127.0.0.1 --port 8000
python -m pytest                            # uses GRADE_TEST_DATABASE_URL or the Docker default
```

On Windows, `.\scripts\run_api_windows.ps1` starts the API. More detail: [`docs/services/backend.md`](../docs/services/backend.md).
