# frontend

> **Audience:** developers working in `frontend/` · **Scope:** what the portal does, configuration, run, build ·
> **Last verified:** 2026-11-09 (`App.jsx`, `vite.config.js`, `src/lib/api.js`, `package.json`)

**Runs as** the Vite dev server on `127.0.0.1:5173`, or as a static build in `dist/` served by any web server. GRADE Companion is
a React 19 single-page app (React Router 7) with no server-side code.

## What it does
| Route | Page | Backend it uses |
|---|---|---|
| `/` | Landing | `/api/exams` |
| `/processing` (`/upload` redirects) | Upload key + sheet, or sheet only; optional layout (empty = detected automatically) | `/jobs/upload-exam-bundle`, `/jobs/upload-sheet` |
| `/evaluator` | Grade a sheet: region preview, per-question OCR text, rubric, score patch | `/jobs/evaluate`, `/result/*`, `/api/sheet/*/preview` |
| `/exams/:examId` | Keys, sheets and stats for one exam | `/api/exams/*` |
| `/dashboard` | Metrics and recent sheets | `/api/metrics/overview`, `/api/sheets` |
| `/reports` | Past results and PDF download | `/api/results`, `/api/sheets`, `/report/*/pdf` |
| `/inspect` | RAG chunk and retrieval debugging | `/api/rag/search`, chunk routes |
| `/settings` | Integration and database status | `/api/integrations`, `/api/database/status` |
| `/docs` | In-app documentation | none |

## Configuration
`VITE_API_URL` (see `frontend/.env.example`): empty in development, so requests go to the same origin and Vite proxies
`/api`, `/health`, `/upload/*`, `/evaluate`, `/result`, `/report`, `/sheet`, `/jobs` to `http://127.0.0.1:8000`. Set it
only when the API runs elsewhere. Everything prefixed `VITE_` is shipped to the browser, so never put a key there.

## Run and build
`cd frontend && npm ci && npm run dev` · `npm run lint` · `npm run build`. There are no frontend unit tests yet.

## Gotchas
- The portal sends a layout only when the teacher types one. Do not pre-fill presets: they were wrong for some sheets
  (`3,1,2,1` was filled in for every 6-question exam).
- The dev proxy sets a 10-minute timeout for `/evaluate` and `/jobs` because multi-question grading is slow. A production
  reverse proxy needs the same, or use the job routes (they return immediately).
- Adding an API route that the portal calls in development means adding its prefix to `proxyPaths` in `vite.config.js`.
