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
    database_status,
    delete_answer_keys_for_exam,
    delete_rag_chunks_for_document,
    get_rag_chunks_for_sheet,
    get_result,
    get_sheet,
    init_db,
    insert_answer_key,
    insert_evaluation_result,
    insert_sheet,
    list_answer_keys,
    list_exams_with_counts,
    list_results,
    list_sheets,
    metrics_overview,
    next_answer_key_sort_order_start,
)
from autograder.embeddings import embed_text_local
from autograder.rag.ingest import ingest_keys_rag, ingest_sheet_rag, keys_document_id, sync_exam_ingest
from autograder.rag.retrieval import (
    hybrid_search_for_exam,
    hybrid_search_for_sheet,
    match_answer_key,
    retrieve_context_for_grading,
)
from autograder.key_pdf import pdf_bytes_to_upload_request
from autograder.ocr import (
    google_vision_configured,
    google_vision_credentials_file_ok,
    ocr_patch,
    ocr_patch_consensus,
)
from autograder.preprocessing import (
    PATCH_SIZE,
    preprocess_pipeline,
    preprocess_sheet_for_evaluation,
)
from autograder.report_pdf import build_evaluation_pdf
from autograder.scoring import prompt_hash, score_answer_llm
from autograder.text_format import format_student_answer
from autograder.schemas import (
    EvaluateRequest,
    EvaluateResponse,
    QuestionResult,
    RubricScores,
    RubricBreakdownResponse,
    UploadExamBundleResponse,
    UploadKeyRequest,
    UploadKeyResponse,
    UploadSheetResponse,
)

logger = logging.getLogger(__name__)


async def _parse_key_upload(
    file: UploadFile,
    exam_id: str | None,
    default_max_marks: float,
) -> UploadKeyRequest:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    name = file.filename.lower()
    raw = await file.read()

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

    raise HTTPException(status_code=400, detail="Upload a .json or text-based .pdf answer key file")


def _save_sheet_bytes(filename: str, data: bytes, exam_id: str) -> UploadSheetResponse:
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
    try:
        sheet_ingest = ingest_sheet_rag(sheet_id, force=True)
    except Exception as e:
        logger.warning("RAG ingest after sheet upload failed sheet=%s: %s", sheet_id, e)
        sheet_ingest = {"status": "error", "detail": str(e)}
    return UploadSheetResponse(sheet_id=sheet_id, filename=filename, exam_id=exid)


def _save_sheet_upload(file: UploadFile, exam_id: str) -> UploadSheetResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    return _save_sheet_bytes(file.filename, file.file.read(), exam_id)


def _preprocess_options_from_env() -> dict:
    """Patch size, PDF zoom, segmentation padding, optional full-page OCR."""
    patch_size = PATCH_SIZE
    raw_ps = os.environ.get("GRADE_OCR_PATCH_SIZE", "").strip()
    if raw_ps:
        try:
            patch_size = max(128, min(2048, int(raw_ps)))
        except ValueError:
            pass
    pdf_render_scale = 3.0
    raw_z = os.environ.get("GRADE_PDF_RENDER_SCALE", "").strip()
    if raw_z:
        try:
            pdf_render_scale = max(1.0, min(6.0, float(raw_z)))
        except ValueError:
            pass
    full_page = os.environ.get("GRADE_OCR_FULL_PAGE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    bbox_padding_frac = 0.04
    raw_pf = os.environ.get("GRADE_OCR_BBOX_PADDING_FRAC", "").strip()
    if raw_pf:
        try:
            bbox_padding_frac = max(0.0, min(0.2, float(raw_pf)))
        except ValueError:
            pass
    bbox_padding_px_min = 16
    raw_pm = os.environ.get("GRADE_OCR_BBOX_PADDING_PX_MIN", "").strip()
    if raw_pm:
        try:
            bbox_padding_px_min = max(0, min(120, int(raw_pm)))
        except ValueError:
            pass
    return {
        "patch_size": patch_size,
        "pdf_render_scale": pdf_render_scale,
        "full_page": full_page,
        "bbox_padding_frac": bbox_padding_frac,
        "bbox_padding_px_min": bbox_padding_px_min,
    }


def _load_dotenv() -> None:
    """Load `.env`: repo root (always), then current working directory (optional overrides)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    # src/autograder/api.py -> parents[2] is repository root (where pyproject.toml lives).
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
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
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
    Answer key file: `.json` (UploadKeyRequest) or text-based `.pdf`.

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
    sheet_resp = _save_sheet_bytes(sheet_file.filename, sheet_bytes, ex)
    keys_ingest = ingest_keys_rag(ex, force=True)
    sheet_ingest = ingest_sheet_rag(sheet_resp.sheet_id, force=True)

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
    if not keys and not sheets:
        raise HTTPException(status_code=404, detail="exam_id not found")
    return {
        "exam": {"id": exam_id, "title": exam_id},
        "keys": keys,
        "sheets": sheets,
    }


@app.post("/upload/sheet", response_model=UploadSheetResponse)
def upload_sheet(
    file: UploadFile = File(...),
    exam_id: str | None = Form(default=None),
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
    return _save_sheet_upload(file, exid)


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
    return FileResponse(
        path,
        filename=row.get("filename") or path.name,
        media_type="application/octet-stream",
    )


@app.post("/api/sheet/{sheet_id}/ingest")
def api_sheet_ingest(sheet_id: str, force: bool = False):
    """Re-run OCR → chunk → embed for an uploaded sheet (populates ``rag_chunks``)."""
    row = get_sheet(sheet_id)
    if not row:
        raise HTTPException(status_code=404, detail="sheet_id not found")
    try:
        return ingest_sheet_rag(sheet_id, force=force)
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
        hits = hybrid_search_rag_chunks(query, qv, top_k=top_k, document_id=None)
    out = []
    for h in hits:
        m = h.get("meta") or {}
        hit_exam_id = (m or {}).get("exam_id")
        if exam_id and hit_exam_id and str(hit_exam_id) != exam_id:
            continue
        fused = h.get("fused_score")
        score = float(fused) if fused is not None else float(1.0 - float(h.get("distance") or 0.0))
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
    sheet = get_sheet(req.sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="sheet_id not found")

    sheet_exam = str(sheet.get("exam_id") or "").strip()
    if sheet_exam and sheet_exam != req.exam_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Sheet is linked to exam '{sheet_exam}' but evaluate requested '{req.exam_id}'. "
                "Re-upload the sheet with the correct exam_id or pick a matching exam."
            ),
        )
    if not sheet_exam:
        raise HTTPException(
            status_code=400,
            detail="Sheet has no exam_id; upload it with the same exam_id as your answer keys.",
        )

    keys = list_answer_keys(req.exam_id)
    if not keys:
        raise HTTPException(status_code=404, detail="No answer keys found for exam_id")

    try:
        pp = preprocess_sheet_for_evaluation(
            sheet["path"],
            num_answer_keys=len(keys),
            expected_num_regions=req.expected_num_regions,
            **_preprocess_options_from_env(),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not pp.patches:
        raise HTTPException(status_code=422, detail="No answer regions detected")

    q_results: List[QuestionResult] = []
    all_flags: List[str] = []
    ocr_engines: List[str] = []
    llm_model = "fallback-legacy"

    try:
        for idx, patch in enumerate(pp.patches):
            ocr_res = (
                ocr_patch_consensus(patch)
                if req.use_consensus_ocr
                else ocr_patch(patch)
            )
            ocr_engines.append(ocr_res.engine)

            raw_ocr = (ocr_res.text or "").strip()
            if not raw_ocr:
                q_results.append(
                    QuestionResult(
                        question_id=keys[min(idx, len(keys) - 1)]["question_id"],
                        region_index=idx,
                        student_answer="",
                        ocr_raw="",
                        awarded_marks=0.0,
                        max_marks=float(keys[min(idx, len(keys) - 1)]["max_marks"]),
                        rubric_scores=RubricScores(
                            factual_accuracy=0,
                            conceptual_completeness=0,
                            reasoning=0,
                            domain_terminology=0,
                        ),
                        feedback="No OCR text detected for this answer region.",
                        grading_confidence="low",
                        ocr_confidence=float(ocr_res.confidence),
                        flags=list(ocr_res.flags or []) + ["ocr_empty", "review_required"],
                    )
                )
                continue

            chosen = match_answer_key(idx, raw_ocr, keys, top_k=req.top_k)
            formatted = format_student_answer(raw_ocr, chosen)
            student_text = formatted.formatted

            rag_ctx = retrieve_context_for_grading(
                req.sheet_id,
                req.exam_id,
                student_text,
                chosen,
                top_k=req.top_k,
                region_index=idx,
            )

            eval_res, llm_model = score_answer_llm(
                student_answer=student_text,
                model_answer=chosen["expected_answer"],
                max_marks=float(chosen["max_marks"]),
                question_text=chosen["question_id"],
                subject_domain=chosen.get("domain") or "general",
                ocr_confidence=float(ocr_res.confidence),
                rubric_override=chosen.get("rubric_override"),
                rag_context=rag_ctx.get("context_text"),
            )

            flags = list(
                set((ocr_res.flags or []) + formatted.flags + eval_res.flags)
            )
            if rag_ctx.get("chunk_ids"):
                flags.append("rag_context_used")
            if formatted.method == "llm":
                flags.append("ocr_llm_formatted")
            all_flags.extend(flags)

            q_results.append(
                QuestionResult(
                    question_id=chosen["question_id"],
                    region_index=idx,
                    student_answer=student_text,
                    ocr_raw=ocr_res.text,
                    awarded_marks=eval_res.awarded_marks,
                    max_marks=eval_res.max_marks,
                    rubric_scores=eval_res.rubric_scores,
                    feedback=eval_res.feedback,
                    grading_confidence=eval_res.grading_confidence,
                    ocr_confidence=ocr_res.confidence,
                    flags=flags,
                )
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("evaluate failed sheet=%s exam=%s", req.sheet_id, req.exam_id)
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {type(e).__name__}: {e}",
        ) from e

    total_marks = round(sum(q.awarded_marks for q in q_results), 1)
    max_total = round(sum(q.max_marks for q in q_results), 1)
    grading_conf = _aggregate_grading_confidence([q.grading_confidence for q in q_results])
    confidence_flag = any(q.ocr_confidence < 0.60 for q in q_results) or grading_conf == "low"

    payload = {
        "sheet_id": req.sheet_id,
        "exam_id": req.exam_id,
        "questions": [q.model_dump() for q in q_results],
        "total_marks": total_marks,
        "max_total": max_total,
        "confidence_flag": confidence_flag,
        "grading_confidence": grading_conf,
        "ocr_engine_used": ",".join(sorted(set(ocr_engines))),
        "prompt_hash": prompt_hash(),
        "llm_model": llm_model,
        "flags": sorted(set(all_flags)),
    }
    result_id = insert_evaluation_result(payload)

    return EvaluateResponse(
        result_id=result_id,
        sheet_id=req.sheet_id,
        exam_id=req.exam_id,
        total_marks=total_marks,
        max_total=max_total,
        confidence_flag=confidence_flag,
        grading_confidence=grading_conf,
        prompt_hash=payload["prompt_hash"],
        llm_model=llm_model,
        flags=payload["flags"],
        questions=q_results,
    )


@app.get("/result/{result_id}", response_model=EvaluateResponse)
def get_result_endpoint(result_id: str):
    row = get_result(result_id)
    if not row:
        raise HTTPException(status_code=404, detail="result_id not found")

    questions = [QuestionResult.model_validate(q) for q in row["questions"]]
    return EvaluateResponse(
        result_id=result_id,
        sheet_id=row.get("sheet_id") or "",
        exam_id=row.get("exam_id") or "",
        total_marks=row["total_marks"],
        max_total=row["max_total"],
        confidence_flag=row["confidence_flag"],
        grading_confidence=row["grading_confidence"],
        prompt_hash=row["prompt_hash"],
        llm_model=row["llm_model"],
        flags=row.get("flags") or [],
        questions=questions,
    )


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
