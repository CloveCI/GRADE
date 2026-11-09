# OCR a whole PDF and store its chunks

> **Audience:** developers checking OCR quality or loading chunks by hand · **Scope:** `backend/scripts/show_grade_workflow.py`
> and `run_ocr_chunk_store.ps1` · **Last verified:** 2026-11-09 (script options checked against the code; not re-run with live OCR)

This is a **diagnostic tool**, separate from grading. It renders a PDF, OCRs every page, shows the OCR confidence, splits the
text into chunks and can store them in `public.rag_chunks`. The chunks are stored under the script's own document id, not
`sheet_{sheet_id}`, so grading never reads them.

## Before you start
From `backend/`:
```powershell
$env:PYTHONPATH = "src"
python -m pip install -e ".[api,ocr_paddle]"     # or ocr_google for Google Vision
```
Use any sheet you have, for example `"cie\sheets\DATA MINING.pdf"`. Local packages in `backend\.dist\python` are loaded
automatically if that folder exists.

## Common runs
| I want to... | Command |
|---|---|
| Check the pipeline without any OCR engine (fake OCR) | `python scripts\show_grade_workflow.py "cie\sheets\DATA MINING.pdf" --mock-ocr --full-page` |
| OCR every page and save the result as JSON | `python scripts\show_grade_workflow.py "cie\sheets\DATA MINING.pdf" --full-page -o extraction.json` |
| Also store the chunks and try a search | `python scripts\show_grade_workflow.py "cie\sheets\DATA MINING.pdf" -o extraction.json --query "apriori algorithm" --top-k 3` |
| Do all of that in one PowerShell command | `.\scripts\run_ocr_chunk_store.ps1 -Pdf "cie\sheets\DATA MINING.pdf"` |

Chunks are stored only when `GRADE_DATABASE_URL` is set in `backend/.env` (add `--no-db` to skip). For OCR, set
`GOOGLE_APPLICATION_CREDENTIALS` or `GOOGLE_CLOUD_VISION_API_KEY` for Vision, or install PaddleOCR.

## Options
| Option | Effect |
|---|---|
| `--page N` | only page *N* (default: every page) |
| `--full-page` | one region per page; often best for notes, where splitting can cut sentences |
| `--expected-regions N` | expect *N* answer regions (falls back to an even grid if detection finds a different number) |
| `--chunk-size 512 --chunk-overlap 96` | chunk length and overlap, in characters |
| `--save-patches DIR` | save the page or region images that were sent to OCR |
| `--consensus` | run cloud OCR and PaddleOCR and keep the more confident result (TrOCR if both fail) |
| `--mock-ocr` | fake OCR text, to test rendering and chunking without an engine |
| `--no-db` | do not store chunks even if a database is configured |
| `--query TEXT --top-k K` | after storing, search the stored chunks |
| `-o FILE` | write the full result as JSON |

`run_ocr_chunk_store.ps1` takes `-Pdf`, `-Output`, `-Query`, `-TopK`, `-FullPage` and `-NoQuery`. Always pass `-Pdf`: its
default file name points at a private scan that is not in the repository.

## What you get
- **On screen:** pages processed, each region's OCR engine, confidence and a text preview, the chunks created, a warning for
  any region below 0.60 confidence, and how many chunks were stored.
- **In the JSON:** `document_id`, `source`, `preprocess.pages`, `regions`, `chunks` (each with page, region, OCR engine and
  confidence, source file) and `full_text`.

## Common problems
| Message | Fix |
|---|---|
| `No module named 'cv2'` | `python -m pip install opencv-python` |
| `PyMuPDF is required for PDF page counting` | `python -m pip install pymupdf` |
| Empty text or `all_tiers_failed` | configure Google Vision, or install an OCR extra: `-e ".[ocr_paddle]"` (also `ocr_google`, `ocr_azure`, `ocr_trocr`) |
| `Install PostgreSQL dependencies` | `python -m pip install "psycopg[binary]" pgvector` |
| Database connection fails | check `GRADE_DATABASE_URL` in `backend/.env`; Supabase pooler URLs need outbound access to port 6543 |

Next: [`runbook.md`](runbook.md) · [`validation.md`](validation.md)
