# Runbook

> **Audience:** whoever runs GRADE for a demo or evaluation · **Scope:** start, check, reset, roll back, incidents ·
> **Last verified:** 2026-11-09

## Deploy
Nothing deploys automatically. `main` is the version you demo or hand in. To run it: start the database, the API and the
portal as in [setup](../getting-started/setup.md). To verify: `GET http://127.0.0.1:8000/health` returns `"status": "ok"` and
`/api/integrations` shows OCR, LLM and database wiring; the portal's **Settings** page shows the same.

## Roll back
Check out the previous good commit on `main` (or revert the bad promotion PR on `staging` and promote again), then restart
the API. The schema only ever adds tables and columns, so older code runs against a newer database.

## Reset local data
```bash
cd backend
docker compose down -v && docker compose up -d     # wipes the database volume
rm -rf data/uploads data/previews                  # uploaded sheets and previews
PYTHONPATH=src python -c "import autograder.api; from autograder.db import init_db; init_db()"
```

## Incidents
| Symptom | Likely cause | What to do |
|---|---|---|
| `/health` says `degraded`, uploads return 503 | Postgres down, wrong `GRADE_DATABASE_URL`, or empty schema | `docker compose ps`; check `/api/database/status`; run `init_db()` |
| `password authentication failed for user "grade"` on 5433 | Another Postgres already owns port 5433 | Stop it, or change the host port in `docker-compose.yml` and the URL |
| Supabase connection fails or resolves to IPv6 | Pooler / DNS issue | `PYTHONPATH=src python scripts/diagnose_pg_dns.py`; `GRADE_PG_PREFER_ADDR_FAMILY`, `GRADE_PG_SKIP_HOSTADDR_RESOLVE` and `GRADE_DATABASE_HOSTADDR` are read in `db.py` (not yet in `.env.example`) |
| Job stuck at a stage | API restarted mid-job (jobs are in-process threads) | Start the job again from the portal |
| OCR text empty | No OCR engine configured | Set `GOOGLE_APPLICATION_CREDENTIALS`; check `/api/integrations` |
| Scores from `fallback-legacy` | LLM disabled or both providers failed | Set `GRADE_ENABLE_LLM=true` and a Gemini or OpenRouter key; check the API log |
| Inspect page / `/api/sheet/{id}/chunks` shows no sheet chunks | The sheet has not been evaluated yet (evaluate indexes it) | Evaluate the sheet, or `POST /api/sheet/{id}/ingest` |
| Questions graded 0 with `region_missing` | Automatic layout could not run (PaddleOCR missing) and no layout was entered | `pip install -e ".[ocr_paddle]"`, or enter the layout, then re-grade |
| Evaluator shows no page images | Previews missing for the sheet | Open the sheet preview with `rebuild=true` (`/api/sheet/{id}/preview?rebuild=true`) |
