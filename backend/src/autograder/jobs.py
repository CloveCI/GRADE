"""Background job runners for long upload/evaluate operations."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional

from autograder.db import create_job, update_job
from autograder.evaluation_service import run_evaluation
from autograder.exam_layouts import parse_regions_per_page
from autograder.schemas import EvaluateRequest

logger = logging.getLogger(__name__)


def _progress(job_id: str):
    def cb(percent: int, stage: str, meta: Optional[dict] = None):
        update_job(job_id, status="running", progress=percent, stage=stage)

    return cb


def start_job_thread(target, *args, **kwargs) -> None:
    t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    t.start()


def run_upload_bundle_job(
    job_id: str,
    *,
    exam_id: str,
    key_bytes: bytes,
    key_filename: str,
    sheet_bytes: bytes,
    sheet_filename: str,
    default_max_marks: float,
    regions_spec: Optional[str],
) -> None:
    from autograder.api import _parse_key_upload_bytes, _save_sheet_bytes, upload_key
    from autograder.db import delete_answer_keys_for_exam, delete_rag_chunks_for_document
    from autograder.rag.ingest import ingest_keys_rag, keys_document_id

    try:
        update_job(job_id, status="running", progress=5, stage="parsing_key")
        payload = _parse_key_upload_bytes(key_bytes, key_filename, exam_id, default_max_marks)
        deleted = delete_answer_keys_for_exam(exam_id)
        delete_rag_chunks_for_document(keys_document_id(exam_id))
        if deleted:
            logger.info("Replaced %s key row(s) for exam_id=%s", deleted, exam_id)

        update_job(job_id, progress=20, stage="ingest_keys")
        key_resp = upload_key(payload)
        update_job(job_id, progress=40, stage="uploading")
        sheet_resp = _save_sheet_bytes(
            sheet_filename,
            sheet_bytes,
            exam_id,
            regions_per_page=None,
            skip_ingest=True,
        )
        ingest_keys_rag(exam_id, force=True)
        # Only the teacher's layout is echoed back; without one, evaluate detects answer positions (layout:auto).
        layout = parse_regions_per_page(regions_spec)
        update_job(
            job_id,
            status="completed",
            progress=100,
            stage="done",
            result={
                "exam_id": exam_id,
                "sheet_id": sheet_resp.sheet_id,
                "filename": sheet_resp.filename,
                "key_ids": key_resp.key_ids,
                "regions_per_page": layout,
                "sheet_ingest": {"status": "deferred", "reason": "ocr_at_evaluate"},
            },
        )
    except Exception as e:
        logger.exception("upload bundle job failed job=%s", job_id)
        update_job(job_id, status="failed", stage="error", error=str(e))


def run_upload_sheet_job(
    job_id: str,
    *,
    exam_id: str,
    sheet_bytes: bytes,
    sheet_filename: str,
    regions_spec: Optional[str],
) -> None:
    from autograder.api import _save_sheet_bytes

    try:
        update_job(job_id, status="running", progress=30, stage="uploading")
        sheet_resp = _save_sheet_bytes(
            sheet_filename, sheet_bytes, exam_id, skip_ingest=True
        )
        layout = parse_regions_per_page(regions_spec)
        update_job(
            job_id,
            status="completed",
            progress=100,
            stage="done",
            result={
                "exam_id": exam_id,
                "sheet_id": sheet_resp.sheet_id,
                "filename": sheet_resp.filename,
                "regions_per_page": layout,
                "sheet_ingest": {"status": "deferred", "reason": "ocr_at_evaluate"},
            },
        )
    except Exception as e:
        logger.exception("upload sheet job failed job=%s", job_id)
        update_job(job_id, status="failed", stage="error", error=str(e))


def run_evaluate_job(job_id: str, payload: Dict[str, Any]) -> None:
    try:
        update_job(job_id, status="running", progress=5, stage="ocr_evaluate")
        req = EvaluateRequest.model_validate(payload)
        result = run_evaluation(req, progress_callback=_progress(job_id))
        update_job(
            job_id,
            status="completed",
            progress=100,
            stage="done",
            result=result.model_dump(),
        )
    except Exception as e:
        logger.exception("evaluate job failed job=%s", job_id)
        update_job(job_id, status="failed", stage="error", error=str(e))


def job_to_response(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": job["id"],
        "job_type": job["job_type"],
        "status": job["status"],
        "progress": int(job.get("progress") or 0),
        "stage": job.get("stage") or "",
        "result": job.get("result"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }
