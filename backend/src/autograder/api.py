"""
FastAPI backend for GRADE — Phases 3–5.

Endpoints: health, integration status, upload key (JSON body or file), upload sheet,
evaluate, result, rubric, PDF report, sheet file download.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from autograder.db import (
    create_job,
    database_status,
    delete_answer_keys_for_exam,
    delete_rag_chunks_for_document,
    get_exam_key_stats,
    get_job,
    get_rag_chunks_for_sheet,
    get_result,
    get_sheet,
    init_db,
    insert_answer_key,
    insert_evaluation_result,
    insert_sheet,
    list_answer_keys,
    list_answer_key_prompts,
    list_exams_with_counts,
    list_results,
    list_sheet_question_answers,
    list_sheets,
    metrics_overview,
    next_answer_key_sort_order_start,
    update_evaluation_question,
)
from autograder.embeddings import embed_text_local
from autograder.rag.ingest import (
    ingest_keys_rag,
    ingest_sheet_rag,
    keys_document_id,
    sheet_document_id,
    sync_exam_ingest,
)
from autograder.rag.retrieval import (
    hybrid_search_for_exam,
    hybrid_search_for_sheet,
    match_answer_key,
    retrieve_context_for_grading,
)
from autograder.key_pdf import pdf_bytes_to_upload_request
from autograder.key_docx import docx_bytes_to_upload_request
from autograder.ocr import (
    google_vision_configured,
    google_vision_credentials_file_ok,
    ocr_patch,
    ocr_patch_consensus,
)
from autograder.preprocessing import PATCH_SIZE, preprocess_options_from_env, preprocess_pipeline, preprocess_sheet_for_evaluation
from autograder.report_pdf import build_evaluation_pdf
from autograder.scoring import aggregate_grading_confidence, prompt_hash, score_answer_llm
from autograder.text_format import format_student_answer
from autograder.schemas import (
    EvaluateRequest,
    EvaluateResponse,
    JobResponse,
    PatchQuestionRequest,
    QuestionResult,
    RubricScores,
    RubricBreakdownResponse,
    UploadExamBundleResponse,
    UploadKeyRequest,
    UploadKeyResponse,
    UploadSheetResponse,
)

logger = logging.getLogger(__name__)

from autograder.exam_layouts import parse_regions_per_page, prompt_from_expected_answer, resolve_regions_per_page


def _resolve_regions_per_page(exam_id: str, req: EvaluateRequest, num_keys: int) -> List[int] | None:
    return resolve_regions_per_page(
        exam_id, regions_per_page=req.regions_per_page, num_keys=num_keys
    )


async def _parse_key_upload(
    file: UploadFile,
    exam_id: str | None,
    default_max_marks: float,
) -> UploadKeyRequest:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    raw = await file.read()
    return _parse_key_upload_bytes(raw, file.filename, exam_id, default_max_marks)


def _parse_key_upload_bytes(
    raw: bytes,
    filename: str,
    exam_id: str | None,
    default_max_marks: float,
) -> UploadKeyRequest:
    name = filename.lower()

    if name.endswith(".json"):
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}") from e
        if exam_id and isinstance(data, dict) and not data.get("exam_id"):
            data["exam_id"] = exam_id.strip()
        try:
            return UploadKeyRequest.model_validate(data)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Schema error: {e}") from e

    if name.endswith(".docx"):
        if not exam_id or not str(exam_id).strip():
            raise HTTPException(
                status_code=400,
                detail="DOCX answer keys require form field exam_id (same exam as the answer sheet).",
            )
        try:
            return docx_bytes_to_upload_request(raw, exam_id.strip(), float(default_max_marks))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    if name.endswith(".pdf"):
        if not exam_id or not str(exam_id).strip():
            raise HTTPException(
                status_code=400,
                detail="PDF answer keys require form field exam_id (same exam as the answer sheet).",
            )
        try:
            return pdf_bytes_to_upload_request(raw, exam_id.strip(), float(default_max_marks))
        except RuntimeError as e:
            raise HTTPException(status_code=501, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    raise HTTPException(status_code=400, detail="Upload a .json, .docx, or text-based .pdf answer key file")


def _save_sheet_bytes(
    filename: str,
    data: bytes,
    exam_id: str,
    *,
    regions_per_page: List[int] | None = None,
    skip_ingest: bool = False,
) -> UploadSheetResponse:
    _require_database(need_rag=True)
    exid = exam_id.strip()
    if not exid:
        raise HTTPException(
            status_code=400,
            detail="exam_id is required so the sheet is linked to the same exam as the answer keys.",
        )

    suffix = Path(filename).suffix or ".png"
    Path("data/uploads").mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="sheet_", suffix=suffix, dir="data/uploads")
    try:
        Path(tmp_path).write_bytes(data)
    finally:
        os.close(fd)

    sheet_id = insert_sheet(filename, tmp_path, exam_id=exid)
    sheet_ingest: dict = {}
    if not skip_ingest:
        try:
            keys = list_answer_keys(exid)
            layout = regions_per_page or resolve_regions_per_page(exid, num_keys=len(keys))
            sheet_ingest = ingest_sheet_rag(sheet_id, force=True, regions_per_page=layout)
        except Exception as e:
            logger.warning("RAG ingest after sheet upload failed sheet=%s: %s", sheet_id, e)
            sheet_ingest = {"status": "error", "detail": str(e)}
    return UploadSheetResponse(sheet_id=sheet_id, filename=filename, exam_id=exid)


def _save_sheet_upload(file: UploadFile, exam_id: str) -> UploadSheetResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    return _save_sheet_bytes(file.filename, file.file.read(), exam_id)


def _preprocess_options_from_env() -> dict:
    return preprocess_options_from_env()


def _load_dotenv() -> None:
    """Load `.env`: backend/ (always), then current working directory (optional overrides)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # src/autograder/api.py -> parents[2] is backend/ folder (where pyproject.toml lives).
    repo_root = Path(__file__).resolve().parents[2]
    try:
        load_dotenv(repo_root / ".env", interpolate=False, override=True)
        load_dotenv(interpolate=False)
    except TypeError:
        load_dotenv(repo_root / ".env", override=True)
        load_dotenv()


_load_dotenv()


def _aggregate_grading_confidence(conf_levels: List[str]) -> str:
    if any(c == "low" for c in conf_levels):
        return "low"
    if any(c == "medium" for c in conf_levels):
        return "medium"
    return "high"


def _cors_origins() -> List[str]:
    raw = os.environ.get(
        "GRADE_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000,http://127.0.0.1:3000",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


def _require_database(*, need_rag: bool = False, need_evaluation: bool = False) -> Dict[str, Any]:
    """Raise 503 when Postgres is not reachable or required tables are missing."""
    st = database_status()
    if not st["configured"]:
        raise HTTPException(
            status_code=503,
            detail=(
                "GRADE_DATABASE_URL is not set. Copy .env.example to .env and use "
                "postgresql://grade:grade@127.0.0.1:5433/grade_test after docker compose up -d."
            ),
        )
    if not st["connected"]:
        raise HTTPException(
            status_code=503,
            detail=st.get("error") or "Database connection failed",
        )
    if not st.get("schema_ready"):
        raise HTTPException(
            status_code=503,
            detail=st.get("error") or "Database schema not ready; restart API after Postgres is up.",
        )
    if need_rag and not st.get("rag_ready"):
        raise HTTPException(
            status_code=503,
            detail="RAG storage not ready (pgvector extension and public.rag_chunks required).",
        )
    if need_evaluation and not st.get("evaluation_ready"):
        raise HTTPException(
            status_code=503,
            detail="Evaluation storage not ready (public.evaluation_results required).",
        )
    return st


@asynccontextmanager
async def lifespan(app: FastAPI):
    st = database_status()
    app.state.database_status = st
    if st.get("connected") and st.get("schema_ready"):
        try:
            init_db()
        except Exception as e:
            logger.exception("init_db failed")
            st = {**st, "connected": False, "schema_ready": False, "error": str(e)}
            app.state.database_status = st
    elif st.get("configured"):
        logger.warning("PostgreSQL unavailable at startup: %s", st.get("error"))
    else:
        logger.warning("GRADE_DATABASE_URL not set; uploads and evaluate will return 503")
    Path("data/uploads").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="GRADE",
    description="Automatic Handwritten Answer Sheet Evaluator",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    db = database_status()
    storage = "postgres" if db.get("connected") else ("configured" if db.get("configured") else "unconfigured")
    return {
        "status": "ok" if db.get("connected") else "degraded",
        "phase": "5",
        "version": "v2-ui",
        "database": db,
        "integrations": {
            "preprocessing": True,
            "ocr": True,
            "storage_backend": storage,
            "rag_ready": bool(db.get("rag_ready")),
            "evaluation_ready": bool(db.get("evaluation_ready")),
            "scoring_llm_fallback": True,
            "pdf_report": True,
        },
    }


@app.get("/api/database/status")
def api_database_status():
    """Postgres + pgvector connectivity for RAG chunks and persisted evaluation results."""
    return database_status()


@app.get("/api/integrations")
def integrations_status():
    """Explicit checklist for Phase 1–6 wiring (useful for QA)."""
    pdf_ok = True
    try:
        import reportlab  # noqa: F401
    except ImportError:
        pdf_ok = False
    pypdf_ok = True
    try:
        import pypdf  # noqa: F401
    except ImportError:
        pypdf_ok = False
    pymupdf_ok = True
    try:
        import fitz  # noqa: F401  # PyMuPDF
    except ImportError:
        pymupdf_ok = False
    from autograder.llm_providers import llm_status

    llm = llm_status()
    db = database_status()

    gcv_installed = True
    try:
        import google.cloud.vision  # noqa: F401
    except ImportError:
        gcv_installed = False
    g_vision_cfg = google_vision_configured()
    g_vision_file = google_vision_credentials_file_ok()
    ocr_cloud_only = os.environ.get("GRADE_OCR_CLOUD_ONLY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ocr_google_only = os.environ.get("GRADE_OCR_GOOGLE_ONLY", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return {
        "phase_1_preprocess": {"module": "autograder.preprocessing", "ok": True},
        "phase_1_sheet_pdf": {"module": "pymupdf", "installed": pymupdf_ok},
        "phase_2_ocr": {
            "module": "autograder.ocr",
            "ok": True,
            "google_cloud_vision_sdk_installed": gcv_installed,
            "google_vision_configured": g_vision_cfg,
            "google_application_credentials_file_ok": g_vision_file,
            "document_text_detection": True,
            "GRADE_OCR_CLOUD_ONLY": ocr_cloud_only,
            "GRADE_OCR_GOOGLE_ONLY": ocr_google_only,
            "ready_google_vision": gcv_installed and g_vision_cfg,
        },
        "llm": llm,
        "llm_gemini": llm.get("llm_gemini"),
        "llm_openrouter": llm.get("llm_openrouter"),
        "phase_3_db": {
            "module": "autograder.db",
            "backend": "postgres",
            **db,
            "ok": bool(db.get("connected") and db.get("schema_ready")),
        },
        "rag_storage": {
            "backend": "public.rag_chunks",
            "pgvector": db.get("pgvector_extension"),
            "ready": db.get("rag_ready"),
            "chunk_count": (db.get("counts") or {}).get("rag_chunks", 0),
        },
        "evaluation_storage": {
            "backend": "public.evaluation_results",
            "ready": db.get("evaluation_ready"),
            "result_count": (db.get("counts") or {}).get("evaluation_results", 0),
        },
        "phase_3_embeddings": {"module": "autograder.embeddings", "ok": True},
        "phase_3_scoring": {"module": "autograder.scoring", "ok": True},
        "phase_3_key_pdf": {"module": "pypdf", "installed": pypdf_ok},
        "phase_4_api": {"ok": True},
        "phase_5_pdf": {"module": "reportlab", "installed": pdf_ok},
        "phase_5_ui": {"note": "Serve frontend via npm run dev", "ok": True},
        "phase_6": {"script": "scripts/verify_phases.py", "ok": True},
    }


@app.post("/upload/key", response_model=UploadKeyResponse)
def upload_key(payload: UploadKeyRequest):
    _require_database(need_rag=True)
    if not payload.questions:
        raise HTTPException(status_code=400, detail="questions cannot be empty")

    sort_base = next_answer_key_sort_order_start(payload.exam_id)
    key_ids: List[str] = []
    for i, q in enumerate(payload.questions):
        key_id = insert_answer_key(
            exam_id=payload.exam_id,
            question_id=q.question_id,
            expected_answer=q.expected_answer,
            embedding=None,
            max_marks=q.max_marks,
            domain=q.domain,
            rubric_override=q.rubric_override,
            sort_order=sort_base + i,
            section=q.section,
            section_pick=q.section_pick,
        )
        key_ids.append(key_id)
    try:
        ingest_keys_rag(payload.exam_id, force=True)
    except Exception as e:
        logger.warning("RAG ingest after key upload failed exam=%s: %s", payload.exam_id, e)
    return UploadKeyResponse(key_ids=key_ids)


@app.post("/upload/key/file", response_model=UploadKeyResponse)
async def upload_key_file(
    file: UploadFile = File(...),
    exam_id: str | None = Form(default=None),
    default_max_marks: float = Form(default=4.0, ge=0.1, le=1000.0),
):
    """
    Answer key file: `.json`, `.docx` (CIE-style), or text-based `.pdf`.

    For PDF, include form field `exam_id` (and optionally `default_max_marks` per question).
    """
    payload = await _parse_key_upload(file, exam_id, default_max_marks)
    return upload_key(payload)


@app.post("/upload/exam-bundle", response_model=UploadExamBundleResponse)
async def upload_exam_bundle(
    exam_id: str = Form(...),
    key_file: UploadFile = File(...),
    sheet_file: UploadFile = File(...),
    default_max_marks: float = Form(default=4.0, ge=0.1, le=1000.0),
    regions_per_page: str | None = Form(default=None),
):
    """
    Upload answer key + sheet together under one ``exam_id``.

    Indexes keys into ``keys_{exam_id}`` and the sheet into ``sheet_{sheet_id}`` for joint RAG retrieval.
    """
    ex = exam_id.strip()
    if not ex:
        raise HTTPException(status_code=400, detail="exam_id is required")

    payload = await _parse_key_upload(key_file, ex, default_max_marks)
    if payload.exam_id.strip() != ex:
        raise HTTPException(
            status_code=400,
            detail=f"Key file exam_id ({payload.exam_id}) does not match form exam_id ({ex})",
        )

    deleted = delete_answer_keys_for_exam(ex)
    delete_rag_chunks_for_document(keys_document_id(ex))
    if deleted:
        logger.info("Replaced %s existing answer key row(s) for exam_id=%s", deleted, ex)

    key_resp = upload_key(payload)
    sheet_bytes = await sheet_file.read()
    if not sheet_file.filename:
        raise HTTPException(status_code=400, detail="Missing sheet filename")
    sheet_resp = _save_sheet_bytes(sheet_file.filename, sheet_bytes, ex, skip_ingest=True)
    keys_ingest = ingest_keys_rag(ex, force=True)
    layout = resolve_regions_per_page(
        ex,
        regions_per_page=parse_regions_per_page(regions_per_page),
        num_keys=len(key_resp.key_ids),
    )
    sheet_ingest = ingest_sheet_rag(sheet_resp.sheet_id, force=True, regions_per_page=layout)
    from autograder.sheet_preview import build_sheet_preview

    build_sheet_preview(sheet_resp.sheet_id, layout=layout)

    return UploadExamBundleResponse(
        exam_id=ex,
        key_ids=key_resp.key_ids,
        sheet_id=sheet_resp.sheet_id,
        filename=sheet_resp.filename,
        keys_ingest=keys_ingest,
        sheet_ingest=sheet_ingest,
    )


@app.post("/api/exam/{exam_id}/ingest-rag")
def api_exam_ingest_rag(exam_id: str, sheet_id: str | None = None):
    """Re-index ``keys_{exam_id}`` and optionally re-ingest a sheet linked to this exam."""
    return sync_exam_ingest(exam_id.strip(), sheet_id=sheet_id)


@app.get("/api/exams")
def api_exams():
    rows = list_exams_with_counts()
    return [
        {
            "id": r.get("exam_id"),
            "title": r.get("title") or r.get("exam_id"),
            "key_count": int(r.get("key_count") or 0),
            "sheet_count": int(r.get("sheet_count") or 0),
            "last_eval_at": r.get("last_eval_at"),
        }
        for r in rows
    ]


@app.get("/api/exams/{exam_id}")
def api_exam_detail(exam_id: str):
    keys = list_answer_keys(exam_id)
    sheets = list_sheets(exam_id=exam_id, limit=1000)
    results = list_results(exam_id=exam_id, limit=100)
    if not keys and not sheets:
        raise HTTPException(status_code=404, detail="exam_id not found")
    stats = get_exam_key_stats(exam_id)
    return {
        "exam": {"id": exam_id, "title": exam_id, **stats},
        "keys": keys,
        "sheets": sheets,
        "results": results,
    }


@app.get("/api/exams/{exam_id}/stats")
def api_exam_stats(exam_id: str):
    keys = list_answer_keys(exam_id)
    if not keys:
        raise HTTPException(status_code=404, detail="exam_id not found")
    return get_exam_key_stats(exam_id)


@app.get("/api/exams/{exam_id}/question-count")
def api_exam_question_count(exam_id: str):
    keys = list_answer_keys(exam_id)
    if not keys:
        raise HTTPException(status_code=404, detail="exam_id not found")
    return {"exam_id": exam_id, "question_count": len(keys)}


def _question_text_by_id(exam_id: str) -> Dict[str, str]:
    rows = list_answer_key_prompts(exam_id)
    return {
        str(row["question_id"]): prompt_from_expected_answer(row.get("expected_answer") or "")
        for row in rows
    }


@app.get("/api/exams/{exam_id}/question-prompts")
def api_exam_question_prompts(exam_id: str):
    rows = list_answer_key_prompts(exam_id)
    if not rows:
        raise HTTPException(status_code=404, detail="exam_id not found")
    return [
        {
            "question_id": row["question_id"],
            "prompt": prompt_from_expected_answer(row.get("expected_answer") or ""),
        }
        for row in rows
    ]


@app.post("/upload/sheet", response_model=UploadSheetResponse)
async def upload_sheet(
    file: UploadFile = File(...),
    exam_id: str | None = Form(default=None),
    regions_per_page: str | None = Form(default=None),
):
    """
    Upload a scanned answer sheet. Pass ``exam_id`` so it pairs with keys for RAG + evaluate.
    """
    exid = exam_id.strip() if exam_id and exam_id.strip() else None
    if not exid:
        raise HTTPException(
            status_code=400,
            detail="exam_id is required on sheet upload (use the same id as your answer keys).",
        )
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    data = await file.read()
    keys = list_answer_keys(exid)
    layout = resolve_regions_per_page(
        exid, regions_per_page=parse_regions_per_page(regions_per_page), num_keys=len(keys)
    )
    return _save_sheet_bytes(file.filename, data, exid, regions_per_page=layout)


@app.get("/api/sheets")
def api_sheets(exam_id: str | None = None, limit: int = 200, offset: int = 0):
    rows = list_sheets(exam_id=exam_id, limit=limit, offset=offset)
    recent = list_results(limit=2000)
    by_sheet: Dict[str, Dict] = {}
    for r in recent:
        sid = str(r.get("sheet_id") or "")
        if sid and sid not in by_sheet:
            by_sheet[sid] = r
    out = []
    for s in rows:
        sid = str(s.get("id") or "")
        rr = by_sheet.get(sid)
        status = "evaluated" if rr else "ingested"
        out.append(
            {
                "id": sid,
                "filename": s.get("filename"),
                "path": s.get("path"),
                "exam_id": s.get("exam_id"),
                "created_at": s.get("created_at"),
                "status": status,
                "ocr_engine": (rr or {}).get("ocr_engine_used") or "unknown",
                "page_count": 1,
            }
        )
    return out


@app.get("/sheet/{sheet_id}/file")
def download_sheet_file(sheet_id: str):
    row = get_sheet(sheet_id)
    if not row:
        raise HTTPException(status_code=404, detail="sheet_id not found")
    path = Path(row["path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored file missing on disk")
    media_type = "application/octet-stream"
    if path.suffix.lower() == ".pdf":
        media_type = "application/pdf"
    elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        media_type = f"image/{path.suffix.lower().lstrip('.')}"
        if media_type == "image/jpg":
            media_type = "image/jpeg"
    return FileResponse(
        path,
        filename=row.get("filename") or path.name,
        media_type=media_type,
        content_disposition_type="inline",
    )


@app.post("/api/sheet/{sheet_id}/ingest")
def api_sheet_ingest(sheet_id: str, force: bool = False, regions_per_page: str | None = None):
    """Re-run OCR → chunk → embed for an uploaded sheet (populates ``rag_chunks``)."""
    row = get_sheet(sheet_id)
    if not row:
        raise HTTPException(status_code=404, detail="sheet_id not found")
    exam_id = str(row.get("exam_id") or "")
    keys = list_answer_keys(exam_id) if exam_id else []
    layout = resolve_regions_per_page(
        exam_id,
        regions_per_page=parse_regions_per_page(regions_per_page),
        num_keys=len(keys),
    )
    try:
        result = ingest_sheet_rag(sheet_id, force=force, regions_per_page=layout)
        from autograder.sheet_preview import build_sheet_preview

        build_sheet_preview(sheet_id, layout=layout)
        return result
    except Exception as e:
        logger.exception("sheet ingest failed sheet=%s", sheet_id)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/sheet/{sheet_id}/chunks")
def api_sheet_chunks(sheet_id: str, limit: int = 500):
    chunks = get_rag_chunks_for_sheet(sheet_id, limit=limit)
    out = []
    for c in chunks:
        m = c.get("meta") or {}
        out.append(
            {
                "chunk_id": c.get("chunk_id"),
                "document_id": c.get("document_id"),
                "chunk_index": c.get("chunk_index"),
                "text": c.get("text_content") or "",
                "page": int((m or {}).get("source_page") or 1),
                "region": (m or {}).get("region_id") or "",
                "ocr_confidence": float((m or {}).get("ocr_confidence") or 0.0),
                "meta": m,
            }
        )
    return out


@app.get("/api/sheet/{sheet_id}/question-regions")
def api_sheet_question_regions(sheet_id: str):
    row = get_sheet(sheet_id)
    if not row:
        raise HTTPException(status_code=404, detail="sheet_id not found")
    return {
        "sheet_id": sheet_id,
        "exam_id": row.get("exam_id"),
        "question_regions": row.get("question_regions") or [],
    }


@app.get("/api/sheet/{sheet_id}/question-answers")
def api_sheet_question_answers(sheet_id: str):
    row = get_sheet(sheet_id)
    if not row:
        raise HTTPException(status_code=404, detail="sheet_id not found")
    return {
        "sheet_id": sheet_id,
        "exam_id": row.get("exam_id"),
        "question_answers": list_sheet_question_answers(sheet_id),
    }


@app.get("/api/results")
def api_results(
    exam_id: str | None = None,
    sheet_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    return list_results(exam_id=exam_id, sheet_id=sheet_id, limit=limit, offset=offset)


@app.get("/api/metrics/overview")
def api_metrics_overview():
    return metrics_overview()


@app.post("/api/rag/search")
def api_rag_search(payload: Dict):
    _require_database(need_rag=True)
    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    top_k = int(payload.get("top_k") or 5)
    sheet_id = str(payload.get("sheet_id") or "").strip() or None
    exam_id = str(payload.get("exam_id") or "").strip() or None
    document_id = None
    if sheet_id:
        s = get_sheet(sheet_id)
        if not s:
            raise HTTPException(status_code=404, detail="sheet_id not found")
        ex = exam_id or str(s.get("exam_id") or "").strip() or None
        if ex:
            hits = hybrid_search_for_exam(sheet_id, ex, query, top_k=top_k)
        else:
            hits = hybrid_search_for_sheet(sheet_id, query, top_k=top_k)
    else:
        from autograder.db import hybrid_search_rag_chunks

        qv = embed_text_local(query)
        doc_ids = None
        if exam_id:
            # Search this exam's own corpora. Searching everything and dropping other exams afterwards
            # could return fewer than top_k hits, or none.
            doc_ids = [keys_document_id(exam_id)] + [
                sheet_document_id(str(s["id"])) for s in list_sheets(exam_id=exam_id, limit=1000)
            ]
        hits = hybrid_search_rag_chunks(query, qv, top_k=top_k, document_ids=doc_ids)
    out = []
    for h in hits:
        m = h.get("meta") or {}
        hit_exam_id = (m or {}).get("exam_id")
        if exam_id and hit_exam_id and str(hit_exam_id) != exam_id:
            continue
        score = float(
            h.get("score")
            if h.get("score") is not None
            else h.get("similarity")
            if h.get("similarity") is not None
            else 1.0 - float(h.get("vector_distance", h.get("distance")) or 1.0)
        )
        out.append(
            {
                "chunk_id": h.get("chunk_id"),
                "document_id": h.get("document_id"),
                "text": h.get("text_content") or "",
                "score": score,
                "page": int((m or {}).get("source_page") or 1),
                "region": (m or {}).get("region_id") or "",
                "sheet_id": sheet_id or m.get("sheet_id"),
                "exam_id": hit_exam_id or exam_id,
            }
        )
    return out


@app.post("/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest):
    _require_database(need_rag=True, need_evaluation=True)
    from autograder.evaluation_service import run_evaluation

    try:
        return run_evaluation(req)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("evaluate failed sheet=%s exam=%s", req.sheet_id, req.exam_id)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {type(e).__name__}: {e}") from e


def _evaluate_response_from_row(result_id: str, row: Dict[str, Any]) -> EvaluateResponse:
    exam_id = str(row.get("exam_id") or "")
    question_texts = _question_text_by_id(exam_id) if exam_id else {}
    questions = []
    for q in row["questions"]:
        item = dict(q)
        if not item.get("question_text"):
            item["question_text"] = question_texts.get(str(item.get("question_id") or ""), "")
        questions.append(QuestionResult.model_validate(item))
    return EvaluateResponse(
        result_id=result_id,
        sheet_id=row.get("sheet_id") or "",
        exam_id=exam_id,
        total_marks=row["total_marks"],
        max_total=row["max_total"],
        confidence_flag=row["confidence_flag"],
        grading_confidence=row["grading_confidence"],
        prompt_hash=row["prompt_hash"],
        llm_model=row["llm_model"],
        flags=row.get("flags") or [],
        questions=questions,
        created_at=row.get("created_at"),
    )


@app.get("/result/{result_id}", response_model=EvaluateResponse)
def get_result_endpoint(result_id: str):
    row = get_result(result_id)
    if not row:
        raise HTTPException(status_code=404, detail="result_id not found")
    return _evaluate_response_from_row(result_id, row)


@app.get("/result/{result_id}/rubric", response_model=RubricBreakdownResponse)
def get_rubric_breakdown(result_id: str):
    row = get_result(result_id)
    if not row:
        raise HTTPException(status_code=404, detail="result_id not found")

    questions = [QuestionResult.model_validate(q) for q in row["questions"]]
    totals: Dict[str, int] = {
        "factual_accuracy": 0,
        "conceptual_completeness": 0,
        "reasoning": 0,
        "domain_terminology": 0,
    }
    for q in questions:
        totals["factual_accuracy"] += q.rubric_scores.factual_accuracy
        totals["conceptual_completeness"] += q.rubric_scores.conceptual_completeness
        totals["reasoning"] += q.rubric_scores.reasoning
        totals["domain_terminology"] += q.rubric_scores.domain_terminology

    return RubricBreakdownResponse(
        result_id=result_id,
        dimension_totals=totals,
        questions=questions,
    )


@app.get("/report/{result_id}/pdf")
def report_pdf(result_id: str):
    row = get_result(result_id)
    if not row:
        raise HTTPException(status_code=404, detail="result_id not found")
    row_full = dict(row)
    row_full["id"] = result_id
    try:
        pdf_bytes = build_evaluation_pdf(row_full)
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="grade-report-{result_id}.pdf"'},
    )


@app.get("/api/exam/{exam_id}/key-chunks")
def api_exam_key_chunks(exam_id: str, limit: int = 500):
    keys = list_answer_keys(exam_id)
    if not keys:
        raise HTTPException(status_code=404, detail="exam_id not found")
    out = []
    for key in keys:
        for ch in (key.get("answer_chunks") or [])[:limit]:
            out.append(
                {
                    "chunk_id": ch.get("chunk_id"),
                    "question_id": key.get("question_id"),
                    "answer_key_id": key.get("id"),
                    "chunk_index": ch.get("chunk_index"),
                    "text": ch.get("text_content") or "",
                    "char_start": ch.get("char_start"),
                    "char_end": ch.get("char_end"),
                }
            )
    return out


@app.get("/api/sheet/{sheet_id}/preview")
def api_sheet_preview_meta(sheet_id: str, rebuild: bool = False):
    row = get_sheet(sheet_id)
    if not row:
        raise HTTPException(status_code=404, detail="sheet_id not found")
    from autograder.sheet_preview import get_sheet_preview

    return get_sheet_preview(sheet_id, force=rebuild)


@app.get("/api/sheet/{sheet_id}/preview/page.png")
def api_sheet_preview_page_legacy(sheet_id: str):
  return api_sheet_preview_page_num(sheet_id, 1)


@app.get("/api/sheet/{sheet_id}/preview/page/{page}.png")
def api_sheet_preview_page_num(sheet_id: str, page: int):
    row = get_sheet(sheet_id)
    if not row:
        raise HTTPException(status_code=404, detail="sheet_id not found")
    from autograder.sheet_preview import build_sheet_preview, preview_page_path

    page_num = max(1, int(page))
    img_path = preview_page_path(sheet_id, page_num)
    if not img_path.is_file():
        build_sheet_preview(sheet_id)
        img_path = preview_page_path(sheet_id, page_num)
    if not img_path.is_file():
        raise HTTPException(status_code=404, detail="preview not available")
    return FileResponse(img_path, media_type="image/png")


@app.patch("/result/{result_id}/questions/{region_index}", response_model=EvaluateResponse)
def patch_result_question(result_id: str, region_index: int, body: PatchQuestionRequest):
    try:
        row = update_evaluation_question(
            result_id,
            region_index,
            awarded_marks=body.awarded_marks,
            feedback=body.feedback,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _evaluate_response_from_row(result_id, row)


@app.post("/jobs/upload-exam-bundle", response_model=JobResponse)
async def job_upload_exam_bundle(
    exam_id: str = Form(...),
    key_file: UploadFile = File(...),
    sheet_file: UploadFile = File(...),
    default_max_marks: float = Form(default=4.0, ge=0.1, le=1000.0),
    regions_per_page: str | None = Form(default=None),
):
    _require_database(need_rag=True)
    ex = exam_id.strip()
    if not ex:
        raise HTTPException(status_code=400, detail="exam_id is required")
    key_bytes = await key_file.read()
    sheet_bytes = await sheet_file.read()
    if not key_file.filename or not sheet_file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    job_id = create_job(
        "upload_bundle",
        {
            "exam_id": ex,
            "key_filename": key_file.filename,
            "sheet_filename": sheet_file.filename,
            "default_max_marks": default_max_marks,
            "regions_per_page": regions_per_page,
        },
    )
    from autograder.jobs import run_upload_bundle_job, start_job_thread

    start_job_thread(
        run_upload_bundle_job,
        job_id,
        exam_id=ex,
        key_bytes=key_bytes,
        key_filename=key_file.filename,
        sheet_bytes=sheet_bytes,
        sheet_filename=sheet_file.filename,
        default_max_marks=default_max_marks,
        regions_spec=regions_per_page,
    )
    return JobResponse(job_id=job_id, job_type="upload_bundle", status="pending", progress=0, stage="")


@app.post("/jobs/upload-sheet", response_model=JobResponse)
async def job_upload_sheet(
    file: UploadFile = File(...),
    exam_id: str = Form(...),
    regions_per_page: str | None = Form(default=None),
):
    _require_database(need_rag=True)
    exid = exam_id.strip()
    if not exid:
        raise HTTPException(status_code=400, detail="exam_id is required")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    data = await file.read()
    job_id = create_job(
        "upload_sheet",
        {"exam_id": exid, "filename": file.filename, "regions_per_page": regions_per_page},
    )
    from autograder.jobs import run_upload_sheet_job, start_job_thread

    start_job_thread(
        run_upload_sheet_job,
        job_id,
        exam_id=exid,
        sheet_bytes=data,
        sheet_filename=file.filename,
        regions_spec=regions_per_page,
    )
    return JobResponse(job_id=job_id, job_type="upload_sheet", status="pending", progress=0, stage="")


@app.post("/jobs/evaluate", response_model=JobResponse)
def job_evaluate(req: EvaluateRequest):
    _require_database(need_rag=True, need_evaluation=True)
    job_id = create_job("evaluate", req.model_dump())
    from autograder.jobs import run_evaluate_job, start_job_thread

    start_job_thread(run_evaluate_job, job_id, req.model_dump())
    return JobResponse(job_id=job_id, job_type="evaluate", status="pending", progress=0, stage="")


@app.get("/jobs/{job_id}", response_model=JobResponse)
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    from autograder.jobs import job_to_response

    data = job_to_response(job)
    return JobResponse(**data)
