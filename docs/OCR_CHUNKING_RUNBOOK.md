# Whole-PDF OCR and Chunking Runbook

This guide explains how to run the GRADE workflow script that renders a PDF, OCRs every page, records OCR confidence, and builds document-level chunks.

## Script

```powershell
scripts\show_grade_workflow.py
```

The script processes the whole PDF by default. Use `--page N` only when you want to inspect one page.

## One-Time Setup

From the repository root:

```powershell
$env:PYTHONPATH = "src"
```

Install project dependencies if needed:

```powershell
python -m pip install -e ".[api,ocr_google]"
```

This workspace also supports local script dependencies in:

```text
.dist\python
```

The workflow script automatically loads `.dist\python` when it exists.

## Demo Run Without OCR Credentials

Use mock OCR to verify PDF rendering, preprocessing, confidence display, and chunking without Google Vision, Azure, PaddleOCR, or TrOCR:

```powershell
python scripts\show_grade_workflow.py "DocScanner 3 Apr 2026 12-56*.pdf" --mock-ocr --full-page
```

Write the complete chunked JSON payload:

```powershell
python scripts\show_grade_workflow.py "DocScanner 3 Apr 2026 12-56*.pdf" --mock-ocr --full-page -o extraction.json
```

## Real OCR Run

Configure at least one OCR engine first. For Google Vision, set one of:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\service-account.json"
```

or:

```powershell
$env:GOOGLE_CLOUD_VISION_API_KEY = "your-api-key"
```

Then run:

```powershell
python scripts\show_grade_workflow.py "DocScanner 3 Apr 2026 12-56*.pdf" --full-page -o extraction.json
```

If `GRADE_DATABASE_URL` is set in `.env`, the script also embeds the generated chunks and upserts them into:

```text
public.rag_chunks
```

Remove `--full-page` if you want contour-based answer-region segmentation instead of one OCR region per page:

```powershell
python scripts\show_grade_workflow.py "DocScanner 3 Apr 2026 12-56*.pdf" -o extraction.json
```

## Exact One-Command Runner

Use this PowerShell script to run the full procedure: load `.env`, OCR the whole PDF, chunk it, write `extraction.json`, store chunks in `public.rag_chunks`, and run a sample retrieval query.

```powershell
.\scripts\run_ocr_chunk_store.ps1
```

Equivalent expanded command:

```powershell
$env:PYTHONPATH = "src"
python scripts\show_grade_workflow.py "DocScanner 3 Apr 2026 12-56*.pdf" -o extraction.json --query "algorithm steps" --top-k 3
```

Options:

```powershell
.\scripts\run_ocr_chunk_store.ps1 -FullPage
```

OCR each page as one full-page region.

```powershell
.\scripts\run_ocr_chunk_store.ps1 -Pdf "path\to\sheet.pdf" -Output "my_extraction.json" -Query "stack operations" -TopK 5
```

Run a different PDF and retrieval query.

```powershell
.\scripts\run_ocr_chunk_store.ps1 -NoQuery
```

Store chunks without running the retrieval test.

## Useful Options

```powershell
--page 2
```

Only process page 2.

```powershell
--full-page
```

OCR each PDF page as one region. This is often best for scanned notes or pages where contour segmentation clips sentences.

```powershell
--expected-regions 5
```

Tell segmentation how many answer regions to expect. If contour detection finds a different count, GRADE uses grid fallback.

```powershell
--chunk-size 512 --chunk-overlap 96
```

Control RAG chunk length and overlap.

```powershell
--save-patches files\patches
```

Save preprocessed page or region images for inspection.

```powershell
--consensus
```

Use OCR consensus mode instead of the normal single tier-chain result.

```powershell
--no-db
```

Skip Postgres storage even when `GRADE_DATABASE_URL` is set.

```powershell
--query "algorithm steps" --top-k 3
```

After storing chunks, run a similarity search against the chunks for this PDF.

## Output

The terminal shows:

- page count and selected pages
- preprocessing diagnostics per page
- OCR engine, confidence, flags, and text preview per region
- chunk IDs, source page, source region, OCR confidence, and chunk preview
- review signal when any OCR confidence is below `0.60`
- database upsert count when `GRADE_DATABASE_URL` is configured

The JSON output contains:

- `document_id`
- `source`
- `preprocess.pages`
- `regions`
- `chunks`
- `chunking`
- `full_text`

Each chunk keeps metadata for:

- `source_page`
- `region_id`
- `ocr_engine`
- `ocr_confidence`
- `source_file`
- `source_path`

## Verification

Check that the script compiles:

```powershell
python -m py_compile scripts\show_grade_workflow.py
```

Check the workflow without live OCR:

```powershell
python scripts\show_grade_workflow.py "DocScanner 3 Apr 2026 12-56*.pdf" --mock-ocr --full-page --chunk-size 120 --chunk-overlap 20
```

Expected behavior for the included sample PDF:

- all pages are processed
- one region per page with `--full-page`
- chunks are created across the whole document
- low OCR confidence regions are listed for manual review

## Common Issues

`ModuleNotFoundError: No module named 'cv2'`

Install OpenCV:

```powershell
python -m pip install opencv-python
```

`PyMuPDF is required for PDF page counting`

Install PyMuPDF:

```powershell
python -m pip install pymupdf
```

OCR returns empty text or `all_tiers_failed`

Configure Google Vision or Azure credentials, or install local OCR extras:

```powershell
python -m pip install -e ".[ocr_google]"
python -m pip install -e ".[ocr_azure]"
python -m pip install -e ".[ocr_paddle]"
python -m pip install -e ".[ocr_trocr]"
```

`Install PostgreSQL dependencies: pip install 'psycopg[binary]' pgvector`

Install database dependencies:

```powershell
python -m pip install "psycopg[binary]" pgvector
```

Database connection fails

Check that `.env` contains `GRADE_DATABASE_URL`. For Supabase pooler URLs, ensure your network allows outbound database connections.
