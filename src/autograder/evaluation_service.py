"""Shared evaluation pipeline for sync API and background jobs."""

from __future__ import annotations

import logging
import re
from typing import Callable, List, Optional

from fastapi import HTTPException

from autograder.db import (
    get_result,
    get_sheet,
    insert_evaluation_result,
    list_answer_keys,
    list_results,
    list_sheet_question_answers,
    upsert_sheet_question_answers,
    update_sheet_question_regions,
)
from autograder.exam_layouts import prompt_from_expected_answer, resolve_regions_per_page
from autograder.ocr import ocr_patch, ocr_patch_consensus
from autograder.rag.boundaries import extract_sheet_answer_span
from autograder.preprocessing import preprocess_sheet_for_evaluation
from autograder.rag.retrieval import retrieve_context_for_grading, retrieve_sheet_answer_for_question
from autograder.schemas import EvaluateRequest, EvaluateResponse, QuestionResult, RubricScores
from autograder.scoring import aggregate_grading_confidence, prompt_hash, score_answer_llm
from autograder.text_format import format_student_answer

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[int, str, dict], None]]


def _token_overlap(a: str, b: str) -> float:
    aw = set(re.findall(r"[a-z]{4,}", (a or "").lower()))
    bw = set(re.findall(r"[a-z]{4,}", (b or "").lower()))
    if not aw or not bw:
        return 1.0
    return len(aw & bw) / max(1, min(len(aw), len(bw)))


def _prompt_coverage(prompt: str, text: str) -> float:
    p = set(re.findall(r"[a-z]{4,}", (prompt or "").lower()))
    t = set(re.findall(r"[a-z]{4,}", (text or "").lower()))
    if not p:
        return 1.0
    return len(p & t) / max(1, len(p))


def question_text_by_id(exam_id: str) -> dict[str, str]:
    from autograder.db import list_answer_key_prompts

    rows = list_answer_key_prompts(exam_id)
    return {
        str(row["question_id"]): prompt_from_expected_answer(row.get("expected_answer") or "")
        for row in rows
    }


def existing_evaluate_response(req: EvaluateRequest) -> EvaluateResponse | None:
    if req.force_regrade:
        return None
    rows = list_results(exam_id=req.exam_id, sheet_id=req.sheet_id, limit=1)
    if not rows:
        return None
    row = get_result(rows[0]["id"])
    if not row:
        return None
    keys = list_answer_keys(req.exam_id)
    questions_raw = row["questions"]
    if keys and len(questions_raw) != len(keys):
        logger.info(
            "Skipping cached result %s: %s questions != %s keys (re-grade with layout required)",
            rows[0]["id"],
            len(questions_raw),
            len(keys),
        )
        return None
    expected_layout = resolve_regions_per_page(
        req.exam_id, regions_per_page=req.regions_per_page, num_keys=len(keys)
    )
    expected_layout_flag = (
        f"layout:{','.join(str(int(n)) for n in expected_layout)}" if expected_layout else None
    )
    existing_flags = set(str(f) for f in (row.get("flags") or []))
    # Invalidate older cached results produced before layout/mapping fixes.
    if expected_layout_flag and expected_layout_flag not in existing_flags:
        logger.info(
            "Skipping cached result %s: missing layout flag %s",
            rows[0]["id"],
            expected_layout_flag,
        )
        return None
    if "segmentation_v3" not in existing_flags:
        logger.info(
            "Skipping cached result %s: missing segmentation_v3 flag",
            rows[0]["id"],
        )
        return None
    questions = [QuestionResult.model_validate(q) for q in questions_raw]
    return EvaluateResponse(
        result_id=rows[0]["id"],
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
        created_at=row.get("created_at"),
    )


def _sync_question_answers_from_evaluation(
    req: EvaluateRequest,
    response: EvaluateResponse,
) -> None:
    """Backfill sheet_question_answers when returning a cached evaluation result."""
    sheet = get_sheet(req.sheet_id)
    if not sheet:
        return
    qr = sheet.get("question_regions") or []
    rows: List[dict] = []
    for q in response.questions:
        idx = int(q.region_index or 0)
        qr_item = next(
            (
                x
                for x in qr
                if int(x.get("question_index") or -1) == idx
                or str(x.get("question_id") or "") == str(q.question_id or "")
            ),
            None,
        )
        rows.append(
            {
                "question_id": str(q.question_id or f"Q{idx + 1}"),
                "question_index": idx,
                "region_index": idx,
                "page_start": int(getattr(q, "page_start", None) or (qr_item or {}).get("page_start") or 1),
                "page_end": int(getattr(q, "page_end", None) or (qr_item or {}).get("page_end") or 1),
                "pages": getattr(q, "pages", None) or (qr_item or {}).get("pages") or [],
                "segments": (qr_item or {}).get("segments") or [],
                "raw_ocr_text": str(q.ocr_raw or ""),
                "formatted_answer_text": str(q.student_answer or ""),
                "format_flags": list(q.flags or []),
                "boundary_confidence": 0.85 if qr_item else 0.5,
            }
        )
    if rows:
        upsert_sheet_question_answers(req.sheet_id, req.exam_id, rows)


def run_evaluation(req: EvaluateRequest, progress_callback: ProgressCallback = None) -> EvaluateResponse:
    cached = existing_evaluate_response(req)
    if cached:
        try:
            _sync_question_answers_from_evaluation(req, cached)
        except Exception as e:
            logger.warning("Could not sync question answers from cache for %s: %s", req.sheet_id, e)
        return cached

    sheet = get_sheet(req.sheet_id)
    if not sheet:
        raise HTTPException(status_code=404, detail="sheet_id not found")

    sheet_exam = str(sheet.get("exam_id") or "").strip()
    if sheet_exam and sheet_exam != req.exam_id:
        raise HTTPException(status_code=400, detail=f"Sheet exam mismatch: {sheet_exam} vs {req.exam_id}")
    if not sheet_exam:
        raise HTTPException(status_code=400, detail="Sheet has no exam_id")

    keys = list_answer_keys(req.exam_id)
    if not keys:
        raise HTTPException(status_code=404, detail="No answer keys found for exam_id")

    question_texts = question_text_by_id(req.exam_id)
    regions_per_page = resolve_regions_per_page(
        req.exam_id, regions_per_page=req.regions_per_page, num_keys=len(keys)
    )

    from autograder.preprocessing import preprocess_options_from_env

    try:
        pp = preprocess_sheet_for_evaluation(
            sheet["path"],
            exam_id=req.exam_id,
            num_answer_keys=len(keys),
            expected_num_regions=req.expected_num_regions,
            regions_per_page=regions_per_page,
            **preprocess_options_from_env(),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not pp.patches:
        raise HTTPException(status_code=422, detail="No answer regions detected")

    # Persist per-sheet question/page/region map for audit + UI consistency.
    qr = []
    for item in (pp.diagnostics.get("question_regions") or []):
        qi = int(item.get("question_index") or 0)
        key = keys[min(qi, len(keys) - 1)] if keys else {}
        qr.append(
            {
                "question_id": str(key.get("question_id") or f"Q{qi + 1}"),
                "question_index": qi,
                "region_index": int(item.get("region_index") or qi),
                "raw_region_indices": item.get("raw_region_indices") or [],
                "region_ids": item.get("region_ids") or [],
                "page_start": int(item.get("page_start") or 1),
                "page_end": int(item.get("page_end") or 1),
                "pages": item.get("pages") or [],
                "segments": item.get("segments") or [],
            }
        )
    try:
        update_sheet_question_regions(req.sheet_id, qr)
    except Exception as e:
        logger.warning("Could not persist sheet question regions for %s: %s", req.sheet_id, e)

    patches = pp.patches[: len(keys)] if len(pp.patches) > len(keys) else pp.patches
    total_patches = len(patches)

    persisted_answers = {
        str(a.get("question_id") or ""): a
        for a in list_sheet_question_answers(req.sheet_id)
    }

    def _qr_for(idx: int, key: Dict[str, Any]) -> Optional[dict]:
        return next(
            (
                x
                for x in qr
                if int(x.get("question_index") or -1) == int(idx)
                or str(x.get("question_id") or "") == str(key.get("question_id") or "")
            ),
            None,
        )

    def _page_fields(qr_item: Optional[dict]) -> dict:
        pages = list(qr_item.get("pages") or []) if qr_item else []
        ps = int((qr_item or {}).get("page_start") or (pages[0] if pages else 1))
        pe = int((qr_item or {}).get("page_end") or (pages[-1] if pages else ps))
        return {"page_start": ps, "page_end": pe, "pages": pages or [ps]}

    q_results: List[QuestionResult] = []
    question_answer_rows: List[dict] = []
    all_flags: List[str] = []
    ocr_engines: List[str] = []
    llm_model = "fallback-legacy"

    for idx, patch in enumerate(patches):
        if progress_callback:
            progress_callback(
                int(10 + (idx / max(total_patches, 1)) * 85),
                "ocr_evaluate",
                {"question_index": idx + 1, "question_total": total_patches},
            )

        key = keys[min(idx, len(keys) - 1)]
        qid = str(key.get("question_id") or "")
        qr_item = _qr_for(idx, key)
        page_info = _page_fields(qr_item)
        stored = persisted_answers.get(qid) or {}
        ocr_parts = (pp.ocr_patch_groups or [[]])[idx] if pp.ocr_patch_groups else [patch]
        if not ocr_parts:
            ocr_parts = [patch]
        ocr_texts: List[str] = []
        ocr_confs: List[float] = []
        ocr_engines_part: List[str] = []
        ocr_flags: List[str] = []
        for ocr_patch_img in ocr_parts:
            ocr_res = ocr_patch_consensus(ocr_patch_img) if req.use_consensus_ocr else ocr_patch(ocr_patch_img)
            ocr_engines_part.append(ocr_res.engine)
            if (ocr_res.text or "").strip():
                ocr_texts.append((ocr_res.text or "").strip())
            ocr_confs.append(float(ocr_res.confidence))
            ocr_flags.extend(ocr_res.flags or [])
        ocr_engines.append(",".join(sorted(set(ocr_engines_part))) or "unknown")
        raw_ocr = "\n\n".join(ocr_texts).strip()
        sheet_rag = retrieve_sheet_answer_for_question(
            req.sheet_id,
            key,
            question_region=qr_item,
            region_ocr=raw_ocr,
        )
        rag_text = (sheet_rag.get("text") or "").strip()
        if rag_text:
            if not raw_ocr or len(rag_text) > len(raw_ocr):
                raw_ocr = rag_text
            elif rag_text not in raw_ocr:
                raw_ocr = f"{raw_ocr}\n\n{rag_text}".strip()
        ocr_confidence = sum(ocr_confs) / len(ocr_confs) if ocr_confs else 0.0
        next_key = keys[idx + 1] if idx + 1 < len(keys) else None
        prev_key = keys[idx - 1] if idx > 0 else None
        _, _, trimmed_ocr = extract_sheet_answer_span(
            raw_ocr, key, next_key, isolated_region=True, prev_key=prev_key
        )
        ocr_for_grading = (trimmed_ocr or raw_ocr).strip()

        if not ocr_for_grading:
            question_answer_rows.append(
                {
                    "question_id": qid or f"Q{idx+1}",
                    "question_index": idx,
                    "region_index": idx,
                    "page_start": page_info["page_start"],
                    "page_end": page_info["page_end"],
                    "pages": page_info["pages"],
                    "segments": (qr_item or {}).get("segments") or [],
                    "raw_ocr_text": raw_ocr,
                    "formatted_answer_text": "",
                    "format_flags": list(set(ocr_flags)) + ["ocr_empty"],
                    "boundary_confidence": 0.85 if qr_item else 0.5,
                }
            )
            q_results.append(
                QuestionResult(
                    question_id=key["question_id"],
                    question_text=question_texts.get(key["question_id"], ""),
                    region_index=idx,
                    page_start=page_info["page_start"],
                    page_end=page_info["page_end"],
                    pages=page_info["pages"],
                    student_answer="",
                    ocr_raw="",
                    awarded_marks=0.0,
                    max_marks=float(key["max_marks"]),
                    rubric_scores=RubricScores(
                        factual_accuracy=0,
                        conceptual_completeness=0,
                        reasoning=0,
                        domain_terminology=0,
                    ),
                    feedback="No OCR text detected for this answer region.",
                    grading_confidence="low",
                    ocr_confidence=float(ocr_confidence),
                    flags=list(set(ocr_flags)) + ["ocr_empty", "review_required"],
                )
            )
            continue

        chosen = keys[min(idx, len(keys) - 1)]
        formatted = format_student_answer(ocr_for_grading, chosen)
        student_text = formatted.formatted
        # Guardrails: reject aggressive rewrites that drift from OCR or prompt intent.
        prompt_text = (
            question_texts.get(chosen["question_id"])
            or prompt_from_expected_answer(str(chosen.get("expected_answer") or ""))
            or str(chosen["question_id"])
        )
        raw_cov = _prompt_coverage(prompt_text, ocr_for_grading)
        fmt_cov = _prompt_coverage(prompt_text, student_text)
        if _token_overlap(ocr_for_grading, student_text) < 0.35 or (fmt_cov + 0.15) < raw_cov:
            student_text = ocr_for_grading
            if "ocr_llm_format_rejected" not in formatted.flags:
                formatted.flags.append("ocr_llm_format_rejected")
        rag_ctx = retrieve_context_for_grading(
            req.sheet_id, req.exam_id, student_text, chosen, top_k=req.top_k, region_index=idx
        )
        eval_res, llm_model = score_answer_llm(
            student_answer=student_text,
            model_answer=str(chosen.get("expected_answer") or ""),
            max_marks=float(chosen["max_marks"]),
            question_text=prompt_text,
            subject_domain=chosen.get("domain") or "general",
            ocr_confidence=float(ocr_confidence),
            rubric_override=chosen.get("rubric_override"),
            rag_context=rag_ctx.get("context_text"),
        )
        flags = list(set(ocr_flags + formatted.flags + eval_res.flags))
        if rag_ctx.get("chunk_ids"):
            flags.append("rag_context_used")
        if sheet_rag.get("chunk_ids"):
            flags.append("sheet_rag_by_question")
        if formatted.method == "llm":
            flags.append("ocr_llm_formatted")
        all_flags.extend(flags)
        q_results.append(
            QuestionResult(
                question_id=chosen["question_id"],
                question_text=question_texts.get(chosen["question_id"], ""),
                region_index=idx,
                page_start=page_info["page_start"],
                page_end=page_info["page_end"],
                pages=page_info["pages"],
                student_answer=student_text,
                ocr_raw=raw_ocr,
                awarded_marks=eval_res.awarded_marks,
                max_marks=eval_res.max_marks,
                rubric_scores=eval_res.rubric_scores,
                feedback=eval_res.feedback,
                grading_confidence=eval_res.grading_confidence,
            ocr_confidence=ocr_confidence,
            flags=flags,
            )
        )
        question_answer_rows.append(
            {
                "question_id": qid or f"Q{idx+1}",
                "question_index": idx,
                "region_index": idx,
                "page_start": page_info["page_start"],
                "page_end": page_info["page_end"],
                "pages": page_info["pages"],
                "segments": (qr_item or {}).get("segments") or [],
                "raw_ocr_text": raw_ocr,
                "formatted_answer_text": student_text,
                "format_flags": list(set(formatted.flags)),
                "boundary_confidence": 0.85 if qr_item else 0.5,
            }
        )

    total_marks = round(sum(q.awarded_marks for q in q_results), 1)
    max_total = round(sum(q.max_marks for q in q_results), 1)
    grading_conf = aggregate_grading_confidence([q.grading_confidence for q in q_results])
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
        "flags": sorted(
            set(all_flags)
            | (
                {
                    f"layout:{','.join(str(int(n)) for n in regions_per_page)}",
                    "segmentation_v3",
                }
                if regions_per_page
                else {"segmentation_v3"}
            )
        ),
    }
    try:
        upsert_sheet_question_answers(req.sheet_id, req.exam_id, question_answer_rows)
    except Exception as e:
        logger.warning("Could not persist sheet question answers for %s: %s", req.sheet_id, e)
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
        created_at=None,
    )
