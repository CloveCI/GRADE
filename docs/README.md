# Documentation

> **Audience:** everyone · **Scope:** the map of all documentation · **Last verified:** 2026-11-08

Start in this order if you are new: [`product.md`](product.md) → [setup](getting-started/setup.md) →
[repo map](getting-started/repo-map.md) → [glossary](getting-started/glossary.md) → [architecture overview](architecture/overview.md).

## By what you are trying to do

| I want to... | Read |
|---|---|
| Understand what GRADE is and what is true today | [`product.md`](product.md) |
| Get the code running | [`getting-started/setup.md`](getting-started/setup.md) |
| Find where something lives | [`getting-started/repo-map.md`](getting-started/repo-map.md) |
| Decode a term (strip, region, layout, rubric...) | [`getting-started/glossary.md`](getting-started/glossary.md) |
| See how the system fits together | [`architecture/overview.md`](architecture/overview.md) |
| Know why something is the way it is | [`architecture/decisions/`](architecture/decisions/README.md) |
| Work on the API or the React portal | [`services/`](services/README.md) |
| Change how a sheet is segmented, read or scored | [`features/grading-pipeline.md`](features/grading-pipeline.md) |
| Ship a change | [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`operations/ci-cd.md`](operations/ci-cd.md) |
| Run, debug or reset a local instance | [`operations/runbook.md`](operations/runbook.md) |
| OCR a whole PDF and store chunks | [`operations/ocr-chunking-runbook.md`](operations/ocr-chunking-runbook.md) |
| Report a security problem | [`../SECURITY.md`](../SECURITY.md) |

## Layout

```
docs/
  product.md         what GRADE is and what is true today
  getting-started/   setup, repo map, glossary
  architecture/      overview, decisions (short records of why)
  services/          one page per component (backend, frontend)
  features/          one page per flagship feature (the grading pipeline)
  operations/        runbook, OCR chunking runbook, CI/CD and security
  _legacy/           older material kept as source for the pages above; may be stale
```

## How these docs stay true

- Every page states its **audience**, **scope** and **last verified** date near the top. CI fails if a page under `docs/` is
  missing the line, or if a relative link is broken (`scripts/ci/check_docs.py`).
- A change that alters behaviour updates the page that describes it in the same pull request. The PR template asks.
- If you find a page that is wrong, fix it or open an issue; do not work around it.
- Material under [`_legacy/`](_legacy/README.md) is not maintained. Do not link to it from new pages except as "source".
