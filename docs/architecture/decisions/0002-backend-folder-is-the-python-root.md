# 0002: `backend/` is the Python project root

- **Status:** Accepted
- **Date:** 2026-11-08

## Context
The Python code finds its files relative to its own location: `api.py` loads `.env` from `Path(__file__).parents[2]`,
`sheet_preview.py` writes to `parents[2] / "data" / "previews"`, tests read `parents[1] / "cie"`, and the scripts use
`parents[1]`. Uploads go to `data/uploads` relative to the working directory. When the API, tests and scripts moved from
the repository root into `backend/`, these all moved together.

## Decision
`backend/` is the Python project root: `pyproject.toml`, `.env`, `data/`, `cie/`, `scripts/` and `tests/` live there, and
every Python command runs from `backend/`. The repository root holds no Python configuration.

## Consequences
- Running the API from the repository root writes uploads to `./data/uploads` but previews to `backend/data/previews`;
  always `cd backend` first. (`/data/` stays gitignored at the root to catch this.)
- Moving any of these folders again means updating the `parents[N]` lookups in the same PR.
