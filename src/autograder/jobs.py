"""Background job runners for long upload/evaluate operations."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, List, Optional

from autograder.db import create_job, get_job, update_job
from autograder.evaluation_service import run_evaluation
from autograder.exam_layouts import parse_regions_per_page, resolve_regions_per_page
from autograder.schemas import EvaluateRequest

logger = logging.getLogger(__name__)

_active_sheet_evaluations: Dict[str, str] = {}
_sheet_eval_lock = threading.Lock()


def sheet_evaluation_busy(sheet_id: str) -> bool:
    release_stale_sheet_lock(sheet_id)
    with _sheet_eval_lock:
        return (sheet_id or "").strip() in _active_sheet_evaluations


def running_evaluate_job_id(sheet_id: str) -> Optional[str]:
    release_stale_sheet_lock(sheet_id)
    with _sheet_eval_lock:
        return _active_sheet_evaluations.get((sheet_id or "").strip())


def release_stale_sheet_lock(sheet_id: str) -> None:
    """Drop in-memory busy flag when the tracked job finished or vanished."""
    sid = (sheet_id or "").strip()
    if not sid:
        return
    with _sheet_eval_lock:
        jid = _active_sheet_evaluations.get(sid)
    if not jid:
        return
    job = get_job(jid)
    if not job or job.get("status") in ("completed", "failed"):
        end_sheet_evaluation(sid)


def clear_sheet_evaluation_lock(sheet_id: str) -> None:
    end_sheet_evaluation(sheet_id)


def try_begin_sheet_evaluation(sheet_id: str, job_id: str) -> bool:
    sid = (sheet_id or "").strip()
    jid = (job_id or "").strip()
    if not sid:
        return True
    release_stale_sheet_lock(sid)
    with _sheet_eval_lock:
        if sid in _active_sheet_evaluations:
            return False
        _active_sheet_evaluations[sid] = jid or sid
        return True


def end_sheet_evaluation(sheet_id: str) -> None:
    sid = (sheet_id or "").strip()
    if not sid:
        return
    with _sheet_eval_lock:
        _active_sheet_evaluations.pop(sid, None)


def _progress(job_id: str):
    def cb(percent: int, stage: str, meta: Optional[dict] = None):
        stage_out = stage
        if meta:
            qi = meta.get("question_index")
            qt = meta.get("question_total")
            if qi is not None and qt:
                stage_out = f"{stage}:{int(qi)}/{int(qt)}"
        try:
            update_job(job_id, status="running", progress=percent, stage=stage_out)
        except Exception as exc:
            logger.warning("Non-fatal job progress update failed job=%s: %s", job_id, exc)

    return cb


def _update_job_safe(job_id: str, **kwargs) -> None:
    try:
        update_job(job_id, **kwargs)
    except Exception as exc:
        logger.error("Job status update failed job=%s: %s", job_id, exc)
        raise


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
        layout = resolve_regions_per_page(
            exam_id,
            regions_per_page=parse_regions_per_page(regions_spec),
            num_keys=len(key_resp.key_ids),
        )
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
    from autograder.db import list_answer_keys

    try:
        update_job(job_id, status="running", progress=30, stage="uploading")
        sheet_resp = _save_sheet_bytes(
            sheet_filename, sheet_bytes, exam_id, skip_ingest=True
        )
        keys = list_answer_keys(exam_id)
        layout = resolve_regions_per_page(
            exam_id,
            regions_per_page=parse_regions_per_page(regions_spec),
            num_keys=len(keys),
        )
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
    req = EvaluateRequest.model_validate(payload)
    if not try_begin_sheet_evaluation(req.sheet_id, job_id):
        try:
            _update_job_safe(
                job_id,
                status="failed",
                stage="error",
                error=(
                    "Another evaluation is already running for this answer sheet. "
                    "Wait for it to finish before starting a new grade."
                ),
            )
        except Exception:
            logger.exception("Could not persist busy status for job=%s", job_id)
        return
    try:
        _update_job_safe(job_id, status="running", progress=5, stage="segment_regions")
        result = run_evaluation(req, progress_callback=_progress(job_id))
        _update_job_safe(
            job_id,
            status="completed",
            progress=100,
            stage="done",
            result=result.model_dump(),
        )
    except Exception as e:
        logger.exception("evaluate job failed job=%s", job_id)
        err_msg = str(e)
        try:
            _update_job_safe(job_id, status="failed", stage="error", error=err_msg)
        except Exception:
            logger.exception("Could not persist failed status for job=%s", job_id)
    finally:
        end_sheet_evaluation(req.sheet_id)


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
