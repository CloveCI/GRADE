# Contributing

## Setup

```bash
git clone https://github.com/Afeef-crypto/GRADE.git && cd GRADE
sh scripts/setup-hooks.sh        # once per clone: hygiene, secrets and lint checks on commit
```

- **backend:** `cd backend && docker compose up -d && pip install -e ".[api,dev]" && cp .env.example .env`, then
  `PYTHONPATH=src python -m uvicorn autograder.api:app --port 8000`. Tests: `python -m pytest` (needs the Docker Postgres;
  on a fresh database run `init_db()` once, see [setup](docs/getting-started/setup.md)).
- **frontend:** `cd frontend && npm ci && npm run dev`. Checks: `npm run lint && npm run build`.

## Workflow

1. Branch from **`staging`**: `feat/short-name`, `fix/short-name`, `chore/...`, `docs/...`. Never branch from or target `main` directly.
2. Keep a PR to one idea. Small PRs get reviewed; large ones get skimmed.
3. Open the PR early. Its **title must be a conventional commit**: `type(scope): summary`, lower-case summary
   (`feat(backend): add per-question regrade`). Types: feat, fix, perf, refactor, test, docs, ci, build, chore, revert.
   Scopes in use: `backend`, `frontend`, `docs`, `ci`, `repo`. PRs into `staging` are squash-merged, so the title becomes the commit.
4. **Open the PR against `staging`.** CI must be green (the single **CI gate** check) and the code owner must approve.
   Fix red before asking for review.
5. **Promote.** When `staging` is in a state you would demo or hand in, open a PR from `staging` to `main` (a merge commit,
   not a squash, so the two branches keep the same history). A PR into `main` from any other branch fails the
   `Only staging can merge into main` check.

`main` and `staging` are protected by repository rulesets (pull request, approval, required checks, no force-push or deletion).
Only a repository admin can bypass them; see [`docs/operations/ci-cd.md`](docs/operations/ci-cd.md).

## Rules that CI enforces

- No `node_modules`, build output, real `.env` files, or files over 1.5 MB in git (the CIE sample scans are allowlisted in
  `.github/large-files-allowlist.txt`).
- No new secret in the diff (gitleaks). Use environment variables; document them in `backend/.env.example` or `frontend/.env.example`.
- Python: no syntax errors or undefined names (ruff `E9,F63,F7,F82`).
- Docs: relative links resolve and every page under `docs/` carries a `Last verified` date.
- Layouts: answer positions are found automatically (`answer_layout.py`); presets in `exam_layouts.py` are only a fallback
  when automatic layout cannot run. Do not reintroduce presets in the portal.
- Schema: a change goes into `db.py` (`init_db`) **and** a new timestamped file in `backend/supabase/migrations/`
  ([ADR 0003](docs/architecture/decisions/0003-schema-in-init-db-and-migrations.md)).

## Commit messages

Imperative, specific, explain *why* in the body when it is not obvious. Example:

```
fix(backend): keep Q4 strips together across pages 2 and 3

The cie-daa layout split Q4a and Q4b into separate questions, so the key count and region count
disagreed and the last question was never graded.
```

## Tests

- Add a test with the fix. Tests mock OCR engines and LLM providers: nothing in CI calls Google, Azure, Gemini or OpenRouter.
  Postgres is real (a pgvector service container in CI, Docker locally).
- Do not weaken or delete a test to make it pass.
- A change to segmentation, automatic layout, OCR, key parsing or scoring can be tested on the CIE samples in `backend/cie/`;
  new results can be added to [`docs/operations/validation.md`](docs/operations/validation.md) in the same PR.

## Security

Do not open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md).

## Documentation

The map is [`docs/README.md`](docs/README.md). A change that alters behaviour updates the page that describes it in the same PR;
CI checks relative links and the `Last verified` line (`python scripts/ci/check_docs.py`).
