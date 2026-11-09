# CI/CD and repository security

> **Audience:** anyone merging or maintaining the pipeline · **Scope:** how code gets from a branch to `main` and what
> stops a bad change on the way · **Last verified:** 2026-11-09 (workflow files validated against the GitHub schema; push and PR runs observed on GitHub)

## Pipeline at a glance

```
feature branch ──► PR to staging ──► CI gate + secret scan + PR title + 1 approval ──► squash merge to staging
                                                                                     │
                                   promotion PR: staging ──► main (merge commit; guard: head must be staging)
                                                                                     │
                                          main = the version that is demoed and handed in (nothing deploys automatically)
```

## Workflows

| Workflow | Trigger | What it does | Blocks merge? |
|---|---|---|---|
| `ci.yml` | PR, push to main/staging | Change detection, repo hygiene, docs check, workflow schema, ruff, backend tests against a pgvector service, frontend lint (report only) and build. Ends in **CI gate**. | Yes: require `CI gate` |
| `security.yml` | PR, push, weekly | gitleaks over the PR's commits, or the full history on push and schedule. One historical false positive (`_anchor_start_for_answer` in `rag/boundaries.py`, commits `3eb533c` and `489d672`) is allow-listed by commit and path in `.github/security/gitleaks.toml` | Yes |
| `pr-hygiene.yml` | PR | Conventional PR title, path labels | Title |
| `promotion-guard.yml` | PR into `main` | Fails unless the head branch is `staging` | Yes |
| `stale.yml` | daily | Closes inactive issues and PRs after 45 + 14 days | No |
| Dependabot | monthly | Grouped minor/patch PRs (Actions, pip in `backend/`, npm in `frontend/`) against `staging` | No |

## What each CI job runs

| Job | Runs when | Commands |
|---|---|---|
| Repo hygiene and docs | always | `scripts/ci/check_repo_hygiene.py`, `scripts/ci/check_docs.py`, `check-jsonschema` on workflows |
| Lint (ruff) | any `.py` or `ruff.toml` changed | `ruff check .` with the narrow rules in `ruff.toml` |
| Backend tests | `backend/**` changed | `pip install -e ".[api,dev]"`, `init_db()`, `pytest` against `pgvector/pgvector:pg16` on port 5433 |
| Frontend | `frontend/**` changed | `npm ci`, `npm run lint` (report only), `npm run build` |

## Branches and protection

`main` and `staging` are protected by rulesets exported in [`.github/rulesets/`](../../.github/rulesets/README.md).
They are not applied yet; see that README for the one-time commands.

## Design choices

- **One required check.** Branch protection requires only `CI gate` (plus the secret scan, PR title and promotion guard);
  jobs skipped by path filters count as passing, so adding a job needs no settings change.
- **Path filters** keep Actions minutes low on pull requests: a docs-only PR costs seconds. Pushes to `main` and `staging`
  run every job, because after a merge or force-push there is no reliable commit to compare against.
- **Real Postgres, mocked providers.** The backend suite needs Postgres + pgvector, so CI runs the same image as
  `backend/docker-compose.yml`. No OCR or LLM keys exist in CI; those calls are mocked in the tests.
- **Explicit schema step.** The API does not create the schema on an empty database
  ([ADR 0003](../architecture/decisions/0003-schema-in-init-db-and-migrations.md)), so CI calls `init_db()` before pytest.
- **Least privilege.** Workflows default to `contents: read`; jobs that need more declare it. Checkouts use
  `persist-credentials: false`.
- **Pinned actions.** Third-party actions are pinned to a commit SHA with the version in a comment.
- **Report first, then enforce.** Frontend lint has 9 existing errors (7 `react-hooks/set-state-in-effect` in
  `EvaluatorPage.jsx`, 2 unused variables in `Topbar.jsx`), so it reports without failing. Ruff is limited to syntax errors and
  undefined names. Both get stricter in their own PRs once the backlog is cleared.
