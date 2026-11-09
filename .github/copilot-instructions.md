# Instructions for Copilot and other coding agents

Read `CONTRIBUTING.md` and `docs/getting-started/repo-map.md` first. Short version:

- **Layout:** `backend/` is the FastAPI API and the `autograder` package (run every Python command from `backend/`);
  `frontend/` is the React + Vite portal; `scripts/ci/` holds CI checks; `docs/` holds the documentation.
- **Branches:** branch from `staging` and open the PR against `staging`. Never target `main`; it only accepts a promotion PR from
  `staging`.
- **PR title:** a conventional commit with a lower-case summary, e.g. `fix(backend): handle empty answer key`. Types: feat, fix,
  perf, refactor, test, docs, ci, build, chore, revert.
- **Tests:** `cd backend && python -m pytest` (needs Postgres from `docker compose up -d`; OCR and LLM calls are mocked);
  `cd frontend && npm run lint && npm run build`. Do not weaken or delete a test to make it pass.
- **Mirrors:** the schema lives in both `db.py` and `backend/supabase/migrations/`; change both together. Answer layout is
  automatic (`answer_layout.py`); exam presets are a backend fallback only.
- **Secrets:** never commit keys, tokens, service-account JSON or `.env` files, and never print them in logs, comments or PR text.
  Use environment variables. Nothing prefixed `VITE_` may hold a secret.
- **Scope:** keep a PR to one idea, and do not reformat unrelated files.
