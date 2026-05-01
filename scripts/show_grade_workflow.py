#!/usr/bin/env python3
"""
Show the GRADE PDF -> preprocessing -> OCR confidence -> chunking workflow.

This script is intentionally explanatory: it runs the same preprocessing and RAG
chunking helpers used by the app, then prints a compact audit trail showing how
PDF pages become OCR regions and how OCR confidence is carried into chunks.

Usage from the repository root:
  $env:PYTHONPATH = "src"
  python scripts/show_grade_workflow.py "DocScanner 3 Apr 2026 12-56 am.pdf" --mock-ocr
  python scripts/show_grade_workflow.py "path/to/sheet.pdf" --page 2 --expected-regions 5
  python scripts/show_grade_workflow.py "path/to/sheet.pdf" --full-page --output workflow.json

Use --mock-ocr when you want to demonstrate the flow without configured OCR
engines. Omit it to call the real OCR tier chain from autograder.ocr.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    env_path = _repo_root() / ".env"
    try:
        from dotenv import load_dotenv
    except ImportError:
        if not env_path.is_file():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return
    try:
        load_dotenv(env_path, interpolate=False, override=True)
    except TypeError:
        load_dotenv(env_path, override=True)
    load_dotenv(interpolate=False)


def _resolve_input(path: Path) -> Path:
    if path.is_absolute():
        candidate = path
    else:
        candidate = (_repo_root() / path)
    raw = str(candidate)
    if any(ch in raw for ch in "*?[]"):
        matches = sorted(candidate.parent.glob(candidate.name))
        files = [p.resolve() for p in matches if p.is_file()]
        if len(files) == 1:
            return files[0]
        if len(files) > 1:
            names = ", ".join(p.name for p in files[:5])
            extra = "" if len(files) <= 5 else f", ... ({len(files)} total)"
            raise ValueError(f"pattern matched multiple files: {names}{extra}")
    return candidate.resolve()


def _shorten(text: str, width: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= width:
        return text
    return text[: max(0, width - 3)] + "..."


def _confidence_label(value: float) -> str:
    if value < 0.60:
        return "LOW"
    if value < 0.80:
        return "MED"
    return "HIGH"


def _print_kv(title: str, data: dict[str, Any]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for key, value in data.items():
        print(f"{key}: {value}")


def _print_rows(headers: list[str], rows: Iterable[list[str]]) -> None:
    rows = list(rows)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        print(fmt.format(*row))


def _pdf_page_count(pdf: Path) -> int:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for PDF page counting. Install: pip install pymupdf") from exc

    doc = fitz.open(pdf)
    try:
        return int(doc.page_count)
    finally:
        doc.close()


def _mock_ocr_result(region_id: str, index: int):
    from autograder.ocr import OCRResult

    samples = [
        (
            "Photosynthesis is the process by which green plants use sunlight, "
            "carbon dioxide, and water to make glucose and release oxygen.",
            0.93,
        ),
        (
            "Mitochondria release energy through respiration. They are often "
            "called the power house of the cell.",
            0.74,
        ),
        (
            "The answr is unclear and may need manual review because handwriting "
            "or scan quality reduced recogniton.",
            0.42,
        ),
    ]
    text, confidence = samples[index % len(samples)]
    low = confidence < 0.60
    flags = ["mock_ocr"]
    if low:
        flags.extend(["ocr_uncertainty", "review_required"])
    return OCRResult(
        text=f"{region_id}: {text}",
        confidence=confidence,
        engine="mock",
        low_confidence=low,
        flags=flags,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Explain the GRADE workflow from PDF preprocessing to OCR confidence and chunks."
    )
    parser.add_argument("pdf", type=Path, help="Answer-sheet PDF to inspect")
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        help="Optional 1-based PDF page number; omit to OCR and chunk the whole PDF",
    )
    parser.add_argument(
        "--expected-regions",
        type=int,
        default=None,
        help="Expected answer-region count; enables grid fallback if contour count differs",
    )
    parser.add_argument(
        "--patch-size",
        type=int,
        default=768,
        help="Square patch size passed to OCR after segmentation",
    )
    parser.add_argument(
        "--pdf-zoom",
        type=float,
        default=3.5,
        help="PyMuPDF render scale for PDF rasterization",
    )
    parser.add_argument(
        "--full-page",
        action="store_true",
        help="Treat the whole page as one OCR region instead of contour chunking",
    )
    parser.add_argument(
        "--bbox-padding",
        type=float,
        default=0.06,
        help="Fraction used to expand detected region boxes before OCR",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Character length for RAG chunks",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=96,
        help="Overlapping characters between adjacent chunks",
    )
    parser.add_argument(
        "--max-regions",
        type=int,
        default=0,
        help="Only OCR the first N regions; 0 means all regions",
    )
    parser.add_argument(
        "--consensus",
        action="store_true",
        help="Use ocr_patch_consensus instead of the normal OCR tier chain",
    )
    parser.add_argument(
        "--mock-ocr",
        action="store_true",
        help="Use deterministic sample OCR results instead of calling OCR engines",
    )
    parser.add_argument(
        "--save-patches",
        type=Path,
        default=None,
        metavar="DIR",
        help="Optional directory for writing preprocessed region PNGs",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Optional path to write the complete RAG JSON payload",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Do not store generated chunks in Postgres, even when GRADE_DATABASE_URL is set",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="After storing chunks, run a similarity search for this query",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of database search hits to show with --query",
    )
    return parser


def _build_whole_pdf_payload(
    *,
    source_path: str,
    page_count: int,
    regions: list[dict[str, Any]],
    preprocess_pages: list[dict[str, Any]],
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, Any]:
    from autograder.rag_extract import chunk_id_for_text, chunk_text, normalize_ocr_text

    fname = source_path.replace("\\", "/").split("/")[-1]
    doc_id = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:12]

    chunks: list[dict[str, Any]] = []
    full_parts: list[str] = []
    chunk_index = 0
    for region in regions:
        rid = str(region.get("region_id") or "R1")
        page = int(region.get("source_page") or 1)
        normalized = normalize_ocr_text(region.get("text") or "")
        full_parts.append(f"[page {page} / {rid}]\n{normalized}")

        for piece, c0, c1 in chunk_text(
            normalized,
            chunk_size=chunk_size,
            overlap=chunk_overlap,
        ):
            cid = chunk_id_for_text(doc_id, chunk_index, piece)
            chunks.append(
                {
                    "chunk_id": cid,
                    "index": chunk_index,
                    "text": piece,
                    "char_start": c0,
                    "char_end": c1,
                    "metadata": {
                        "region_id": rid,
                        "ocr_engine": region.get("ocr_engine"),
                        "ocr_confidence": region.get("ocr_confidence"),
                        "source_page": page,
                        "source_file": fname,
                        "source_path": source_path,
                    },
                }
            )
            chunk_index += 1

    return {
        "schema_version": "1.0",
        "kind": "grade_ocr_extraction",
        "document_id": doc_id,
        "source": {
            "type": "application/pdf",
            "filename": fname,
            "path": source_path,
            "page_count": page_count,
        },
        "preprocess": {
            "pages": preprocess_pages,
        },
        "full_text": normalize_ocr_text("\n\n".join(full_parts)),
        "regions": regions,
        "chunks": chunks,
        "chunking": {
            "chunk_size": chunk_size,
            "overlap": chunk_overlap,
            "chunk_count": len(chunks),
        },
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    _load_dotenv()
    os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

    args = build_arg_parser().parse_args()
    if args.page is not None and args.page < 1:
        print("[fail] --page must be >= 1", file=sys.stderr)
        return 1
    if args.patch_size < 128 or args.patch_size > 2048:
        print("[fail] --patch-size must be between 128 and 2048", file=sys.stderr)
        return 1

    repo = _repo_root()
    os.chdir(repo)
    local_deps = repo / ".dist" / "python"
    if local_deps.is_dir():
        sys.path.insert(0, str(local_deps))
    sys.path.insert(0, str(repo / "src"))

    try:
        pdf = _resolve_input(args.pdf)
    except ValueError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1
    if not pdf.is_file():
        print(f"[fail] PDF not found: {pdf}", file=sys.stderr)
        return 1
    if pdf.suffix.lower() != ".pdf":
        print(f"[fail] expected a .pdf file: {pdf}", file=sys.stderr)
        return 1

    from autograder.preprocessing import preprocess_pipeline
    from autograder.rag_extract import normalize_ocr_text, rag_payload_to_json

    try:
        page_count = _pdf_page_count(pdf)
    except RuntimeError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        return 1
    pages = [args.page] if args.page is not None else list(range(1, page_count + 1))
    for page in pages:
        if page > page_count:
            print(f"[fail] PDF page {page} out of range; document has {page_count} pages", file=sys.stderr)
            return 1

    print("GRADE PDF Workflow")
    print("==================")
    _print_kv(
        "Input",
        {
            "pdf": pdf,
            "pages": f"{pages[0]}..{pages[-1]}" if len(pages) > 1 else str(pages[0]),
            "page_count": page_count,
            "mode": "mock OCR" if args.mock_ocr else "real OCR tier chain",
        },
    )

    if args.consensus and args.mock_ocr:
        print("\n[warn] --consensus is ignored with --mock-ocr")

    if args.mock_ocr:
        ocr_fn = None
    elif args.consensus:
        from autograder.ocr import ocr_patch_consensus as ocr_fn
    else:
        from autograder.ocr import ocr_patch as ocr_fn

    regions: list[dict[str, Any]] = []
    region_rows: list[list[str]] = []
    preprocess_pages: list[dict[str, Any]] = []
    global_region_index = 0

    for page in pages:
        print(f"\n[1] Render page {page} and segment answer regions")
        pre = preprocess_pipeline(
            pdf,
            expected_num_regions=args.expected_regions,
            patch_size=args.patch_size,
            pdf_page_index=page - 1,
            pdf_render_scale=max(1.0, min(6.0, float(args.pdf_zoom))),
            full_page=args.full_page,
            bbox_padding_frac=max(0.0, min(0.2, float(args.bbox_padding))),
            bbox_padding_px_min=0 if args.bbox_padding <= 0 else 20,
        )
        preprocess_pages.append(
            {
                "page": page,
                "regions_found": len(pre.patches),
                "fallback_grid": pre.used_fallback_grid,
                "patch_size": args.patch_size,
                "pdf_render_scale": max(1.0, min(6.0, float(args.pdf_zoom))),
                "full_page": args.full_page,
                "diagnostics": pre.diagnostics,
            }
        )
        _print_kv(
            f"Preprocessing Page {page}",
            {
                "regions_found": len(pre.patches),
                "fallback_grid": pre.used_fallback_grid,
                "patch_size": f"{args.patch_size}x{args.patch_size}",
                "diagnostics": json.dumps(pre.diagnostics, sort_keys=True),
            },
        )

        if args.save_patches:
            import cv2

            patch_dir = _resolve_input(args.save_patches)
            patch_dir.mkdir(parents=True, exist_ok=True)
            for i, patch in enumerate(pre.patches):
                local_rid = pre.region_ids[i] if i < len(pre.region_ids) else f"R{i + 1}"
                cv2.imwrite(str(patch_dir / f"P{page}_{local_rid}.png"), patch)

        print(f"\n[2] OCR page {page} regions and record confidence")
        region_limit = args.max_regions if args.max_regions and args.max_regions > 0 else len(pre.patches)
        for i, patch in enumerate(pre.patches[:region_limit]):
            local_rid = pre.region_ids[i] if i < len(pre.region_ids) else f"R{i + 1}"
            rid = f"P{page}_{local_rid}"
            bbox = pre.bboxes[i] if i < len(pre.bboxes) else None
            if args.mock_ocr:
                res = _mock_ocr_result(rid, global_region_index)
            else:
                res = ocr_fn(patch, retry_delay=0.0)  # type: ignore[misc]

            text = res.text or ""
            regions.append(
                {
                    "region_id": rid,
                    "source_page": page,
                    "text": text,
                    "ocr_engine": res.engine,
                    "ocr_confidence": float(res.confidence),
                    "flags": list(res.flags or []),
                    "bbox": bbox,
                }
            )
            region_rows.append(
                [
                    str(page),
                    rid,
                    str(bbox),
                    res.engine,
                    f"{res.confidence:.3f}",
                    _confidence_label(float(res.confidence)),
                    ",".join(res.flags or []),
                    _shorten(text, 64),
                ]
            )
            global_region_index += 1

    if args.save_patches:
        print(f"\n[wrote patches] {_resolve_input(args.save_patches)}")

    _print_rows(
        ["page", "region", "bbox", "engine", "conf", "level", "flags", "text preview"],
        region_rows,
    )

    print("\n[3] Normalize OCR text and build document-level RAG chunks")
    payload = _build_whole_pdf_payload(
        source_path=str(pdf),
        page_count=page_count,
        regions=regions,
        preprocess_pages=preprocess_pages,
        chunk_size=max(64, int(args.chunk_size)),
        chunk_overlap=max(0, int(args.chunk_overlap)),
    )

    chunk_rows: list[list[str]] = []
    for chunk in payload["chunks"]:
        meta = chunk.get("metadata") or {}
        conf = float(meta.get("ocr_confidence") or 0.0)
        chunk_rows.append(
            [
                str(chunk["index"]),
                str(meta.get("source_page")),
                str(meta.get("region_id")),
                f"{chunk['char_start']}..{chunk['char_end']}",
                f"{conf:.3f}",
                _confidence_label(conf),
                chunk["chunk_id"],
                _shorten(chunk.get("text") or "", 72),
            ]
        )

    _print_kv(
        "Chunking Summary",
        {
            "document_id": payload["document_id"],
            "chunk_size": payload["chunking"]["chunk_size"],
            "overlap": payload["chunking"]["overlap"],
            "chunk_count": payload["chunking"]["chunk_count"],
            "full_text_chars": len(normalize_ocr_text(payload.get("full_text") or "")),
        },
    )
    if chunk_rows:
        _print_rows(
            ["idx", "page", "region", "chars", "ocr_conf", "level", "chunk_id", "chunk preview"],
            chunk_rows,
        )
    else:
        print("No chunks were produced because OCR text was empty.")

    low_regions = [r["region_id"] for r in regions if float(r["ocr_confidence"]) < 0.60]
    print("\n[4] Review signal")
    if low_regions:
        print(
            "Manual review recommended: "
            f"{', '.join(low_regions)} had OCR confidence below 0.60."
        )
    else:
        print("No OCR region fell below the 0.60 review threshold.")

    if args.output:
        out_path = _resolve_input(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rag_payload_to_json(payload, pretty=True), encoding="utf-8")
        print(f"\n[wrote JSON] {out_path}")

    if args.no_db:
        print("\n[db] skipped because --no-db was set")
    elif not (os.environ.get("GRADE_DATABASE_URL") or os.environ.get("DATABASE_URL")):
        print("\n[db] skipped because GRADE_DATABASE_URL is not set")
    elif not payload.get("chunks"):
        print("\n[db] skipped because no chunks were produced")
    else:
        print("\n[5] Store chunks in grade database")
        try:
            from autograder.db import init_db, search_rag_chunks, upsert_rag_chunks_batch
            from autograder.embeddings import embed_text_local
            from autograder.rag_extract import rag_rows_for_postgres

            rows = rag_rows_for_postgres(payload, embed_fn=embed_text_local)
            init_db()
            stored = upsert_rag_chunks_batch(rows)
            print(
                f"[db] upserted {stored} chunks into public.rag_chunks "
                f"for document_id={payload['document_id']}"
            )

            if args.query:
                hits = search_rag_chunks(
                    embed_text_local(args.query),
                    top_k=max(1, int(args.top_k)),
                    document_id=payload.get("document_id"),
                )
                print("\n[db] query results")
                if not hits:
                    print("No matching chunks found.")
                else:
                    for hit in hits:
                        dist = float(hit.get("distance") or 0.0)
                        chunk_id = str(hit.get("chunk_id") or "")
                        preview = _shorten(hit.get("text_content") or "", 96)
                        print(f"distance={dist:.4f}  chunk={chunk_id}  {preview}")
        except Exception as exc:
            print(f"[db fail] {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
