# GRADE (Generalized Recognition and Automated Document Evaluator)

**Automatic Handwritten Answer Sheet Evaluator** — scans, recognises, and grades handwritten exam answers with minimal human intervention.

---

## About

GRADE ingests **answer keys** (Word `.docx`, JSON, or text PDF) and **student sheets** (PDF or image), segments each page into horizontal answer regions (OpenCV + ink-aware strip boundaries), runs **OCR** with a tiered stack, retrieves **model-answer context** via hybrid RAG (local embeddings + pgvector + FTS), and **scores** each question with an **LLM rubric** (Gemini primary, OpenRouter fallback) or a **legacy embedding fallback** when LLM is disabled.

Results are stored in **PostgreSQL**, exposed through **FastAPI**, reviewed in the **React portal**, and exported as a **ReportLab PDF**.

- **Objective:** Reliable grading for open-ended handwritten responses in CIE-style multi-question layouts.
- **Implementation plan:** See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) (v2 rubric + RAG direction).

### Pipeline (current)

```mermaid
flowchart LR
  A[Upload key + sheet] --> B[Save sheet to disk]
  B --> C[Index answer keys RAG]
  C --> D[Evaluate job]
  D --> E[Segment strips per layout]
  E --> F[OCR per region]
  F --> G[RAG + boundary trim]
  G --> H[LLM rubric score]
  H --> I[Result + PDF + UI preview]
```

**Upload is fast:** sheet OCR/RAG ingest is **deferred** until evaluate (`sheet_ingest: deferred`). Answer keys are indexed into `rag_chunks` on bundle upload.

**Evaluate** runs segmentation (`segmentation_v3`), per-question OCR, boundary-aware answer extraction, rubric scoring, and persists `sheet_question_regions` + `sheet_question_answers` for the evaluator UI.

---

## Tech stack (as implemented)

| Layer | Technology |
|-------|------------|
| **Preprocessing** | OpenCV — deskew, horizontal strip segmentation, ink-aware split bounds, multi-page merge |
| **OCR / HTR** | **Google Cloud Vision** (tier 1 when configured), Azure, PaddleOCR, TrOCR |
| **Layouts** | Exam presets (`cie-daa`, `cie-dm`) + per-page region counts; multi-strip merge for spanning answers (e.g. Q4 across two pages) |
| **Embeddings / RAG** | Local hash embeddings (`embed_text_local`, 128-D) or optional Sentence-Transformers; **pgvector** + FTS on `rag_chunks` and `answer_key_chunks` |
| **Scoring** | Gemini (`GRADE_ENABLE_LLM` + `GRADE_GEMINI_API_KEY`); OpenRouter fallback; legacy cosine fallback |
| **Backend** | FastAPI + background **jobs** (`/jobs/*`, polled by the UI) |
| **Frontend** | React 19 + Vite (`frontend-react/`) — upload, evaluator with region preview, dashboard, reports |
| **Storage** | **PostgreSQL + pgvector** (`GRADE_DATABASE_URL` required); files on disk under `data/` |
| **Report** | ReportLab PDF |

Install extras as needed:

```bash
pip install -e ".[api]"              # FastAPI, Postgres, PDF, PyMuPDF
pip install -e ".[ocr_google]"       # Google Cloud Vision
pip install -e ".[llm_gemini]"       # Gemini grading
pip install -e ".[embeddings]"       # Optional Sentence-Transformers backend
```

---

## Repository structure (high level)

```
GRADE/
├── cie/                     # Sample keys (.docx) and sheets (.pdf) for CIE subjects
├── data/
│   ├── uploads/             # Uploaded sheet files (sheet_<random>.pdf)
│   └── previews/{sheet_id}/ # Rendered page PNGs + regions.json for the UI
├── docs/                    # ARCHITECTURE.md, IMPLEMENTATION_PLAN.md, OCR runbook
├── frontend-react/          # GRADE Companion UI (React + Vite)
├── frontend/                # npm scripts delegate to frontend-react/
├── scripts/                 # verify_*, RAG/OCR utilities, e2e helpers
├── src/autograder/          # api, db, preprocessing, ocr, scoring, rag/, jobs, …
├── supabase/migrations/     # Postgres + pgvector schema (Supabase-compatible)
├── tests/                   # 143+ pytest cases (API, RAG, layouts, OCR mocks)
├── docker-compose.yml       # Local Postgres 16 + pgvector on port 5433
├── pyproject.toml
└── README.md
```

---

## Configuration (`.env`)

Create a `.env` file in the **repo root** (see variable names below; copy from your team's template if provided).

| Variable | Purpose |
|----------|---------|
| `GRADE_DATABASE_URL` | **Required** for the API — Postgres URI (see Docker below) |
| `GRADE_TEST_DATABASE_URL` | Optional — separate DB for `pytest` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON (**recommended for Vision OCR**) |
| `GOOGLE_CLOUD_VISION_API_KEY` | Alternative to JSON for Vision API |
| `GRADE_OCR_GOOGLE_ONLY` | Cloud tier uses only Google (no Azure fallback) |
| `GRADE_OCR_CLOUD_ONLY` | No local PaddleOCR/TrOCR fallback |
| `GRADE_PDF_RENDER_SCALE` | PDF render zoom for segmentation/OCR (default `3.0`) |
| `GRADE_OCR_PATCH_SIZE` | OCR patch size in pixels (default `384`) |
| `GRADE_ENABLE_LLM` | Enable LLM rubric grading |
| `GRADE_GEMINI_API_KEY` | Gemini API key |
| `GRADE_LLM_MODEL` | Gemini model (default `gemini-2.0-flash`) |
| `GRADE_OPENROUTER_API_KEY` | OpenRouter fallback when Gemini fails |
| `GRADE_OPENROUTER_MODEL` | OpenRouter model (default `google/gemini-2.5-flash-lite`) |
| `GRADE_EMBED_BACKEND` | Set to `hash` to force deterministic local embeddings (tests) |

Passwords with **`$`** in URLs: loaders use `interpolate=False` so `.env` values are not mangled.

---

## Getting started

1. **Clone** and **install:**
   ```powershell
   pip install -e ".[api,ocr_google,llm_gemini]"
   ```
2. **Database:** use **Docker** (below) or any PostgreSQL 16+ with pgvector. Set `GRADE_DATABASE_URL` in `.env`. The API runs `init_db()` on startup (no manual SQL for a fresh local DB). For **Supabase**, apply `supabase/migrations/` via the SQL editor or CLI.
3. **Configure** `.env` (Vision credentials, `GRADE_DATABASE_URL`, optional Gemini/OpenRouter).
4. **Run API** (from repo root):
   ```powershell
   $env:PYTHONPATH = "src"
   python -m uvicorn autograder.api:app --host 127.0.0.1 --port 8000
   ```
5. **Run UI:**
   ```powershell
   cd frontend-react
   npm install
   npm run dev
   ```
   Open the URL Vite prints (often `http://127.0.0.1:5173`). (`cd frontend` also works — it delegates to `frontend-react`.)
6. **Tests:** `python -m pytest` needs Postgres (default matches Docker below; override with `GRADE_TEST_DATABASE_URL`).

In dev, leave `VITE_API_URL` empty (`frontend-react/.env.example`) — Vite proxies API routes to `http://127.0.0.1:8000`.

---

## Portal UI (`frontend-react/`)

The **GRADE Companion** React app talks to FastAPI. Long operations use **background jobs** (`POST /jobs/*` → poll `GET /jobs/{id}`).

| UI route | Purpose |
|----------|---------|
| `/` | Landing |
| `/processing` | Upload marking scheme + sheet (or sheet only); auto layout hints |
| `/evaluator` | Grade sheet — region preview, per-question OCR, rubric, HITL score patch |
| `/exams/:examId` | Exam detail — keys, sheets, stats |
| `/dashboard` | Metrics and recent sheets |
| `/reports` | Past results and PDF download |
| `/inspect` | RAG chunk / retrieval debugging |
| `/settings` | Integration and database status |
| `/docs` | In-app documentation |

| UI action | Backend |
|-----------|---------|
| Upload bundle | `POST /jobs/upload-exam-bundle` |
| Upload sheet only | `POST /jobs/upload-sheet` |
| Grade | `POST /jobs/evaluate` → `GET /result/{id}` |
| Sheet preview | `GET /api/sheet/{id}/preview`, `…/preview/page/{n}.png` |
| PDF report | `GET /report/{id}/pdf` |

Backend config stays in the **repo root** `.env`. The UI only needs `VITE_API_URL` when the API runs on another host (production).

---

## Exam layouts

CIE-style sheets use a **comma-separated layout** — one integer per PDF page = number of horizontal answer strips on that page. Presets live in `src/autograder/exam_layouts.py` (mirrored in `frontend-react/src/lib/examLayouts.js`).

| Exam id | Layout | Notes |
|---------|--------|-------|
| `cie-daa` (aliases `daa`, `daa1`) | `3,1,2,1` | P1=Q1–Q3; P2=Q4a; P3=Q4b+Q5; P4=Q6 — **Q4 merges strips across pages 2–3** |
| `cie-dm` | `2,2,1,1,1` | DATA MINING sample — 7 raw strips merged into 6 keys |

Upload auto-fills layout from exam id. Cached grades are invalidated when the resolved layout changes (`layout:…` flag on results).

---

## On-disk data

| Path | Contents |
|------|----------|
| `data/uploads/sheet_*.pdf` | Raw uploaded sheets (path also stored in `sheets.path`) |
| `data/previews/{sheet_id}/` | `pageN.png`, `regions.json` for evaluator overlays |

Answer keys are stored in Postgres (`answer_keys`, `answer_key_chunks`); only sheet binaries are kept on disk.

---

## API highlights

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness |
| `GET /api/integrations` | OCR, LLM, DB wiring checklist |
| `POST /upload/key`, `/upload/key/file` | Sync key upload (JSON, DOCX, PDF) |
| `POST /upload/exam-bundle` | Sync bundle upload |
| `POST /jobs/upload-exam-bundle` | Async bundle (used by UI) |
| `POST /jobs/evaluate` | Async grading |
| `GET /jobs/{job_id}` | Job progress (`stage`, `progress`, `result`) |
| `GET /api/sheets`, `/api/exams` | Inventory |
| `GET /sheet/{id}/file` | Download original sheet |
| `POST /api/rag/search` | Hybrid retrieval debug |
| `GET /result/{id}/rubric` | Per-question rubric breakdown |

---

## Sample assets (`cie/`)

Bundled **marking schemes** (`cie/keys/*.docx`) and **scanned sheets** (`cie/sheets/*.pdf`) for subjects such as DAA, Data Mining, Compiler Design, Cryptography, and Disaster Mitigation. Use these with matching `exam_id` values (e.g. `daa`, `cie-dm`) when testing uploads.

---

## Docker (local PostgreSQL + pgvector)

1. Install **[Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)** and enable the **WSL 2** backend if prompted.
2. **Start Docker Desktop** and wait until it shows **Running**.
3. From the repo root:
   ```powershell
   docker compose up -d
   docker compose ps
   ```
   Postgres should be **healthy** on host port **5433** (avoids clashing with a local Postgres on 5432).
4. In `.env`:
   ```text
   GRADE_DATABASE_URL=postgresql://grade:grade@127.0.0.1:5433/grade_test
   ```
   To keep **Supabase** for the API but run **tests** against Docker, leave `GRADE_DATABASE_URL` as-is and set `GRADE_TEST_DATABASE_URL` to the URL above.
5. Smoke test:
   ```powershell
   $env:PYTHONPATH = "src"
   $env:GRADE_DATABASE_URL = "postgresql://grade:grade@127.0.0.1:5433/grade_test"
   python scripts/verify_postgres_db.py
   ```

---

## Verification scripts

```powershell
$env:PYTHONPATH = "src"
python scripts/verify_phases.py
python scripts/verify_key_pdfs.py          # parses docs/Key.pdf + DocScanner*.pdf if present
python scripts/verify_postgres_db.py       # needs GRADE_DATABASE_URL
python scripts/test_rag_ingestion_retrieval.py   # RAG ingest + search smoke test
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design (diagram may predate LLM/RAG details) |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Phased plan and v2 rubric spec |
| [docs/OCR_CHUNKING_RUNBOOK.md](docs/OCR_CHUNKING_RUNBOOK.md) | Whole-PDF OCR, confidence reporting, chunk export |

---

## Team

- Md Afeeduddin  
- Syed Liyaqat  

*B.E. Computer Science Engineering — Academic Mini Project (GRADE v2)*

---

## License

Academic project — see institution guidelines.
