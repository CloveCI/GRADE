from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from autograder.embeddings import cosine_similarity, embed_text_local
from autograder.llm_providers import (
    build_grading_user_prompt,
    gemini_api_key,
    gemini_model,
    grading_system_prompt,
    openrouter_chat,
    openrouter_fallback_enabled,
    openrouter_model,
)
from autograder.schemas import EvaluationResult, RubricScores, RUBRIC_SCALE_MAX

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "grading_v2.txt"


def prompt_hash() -> str:
    payload = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else ""
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def aggregate_grading_confidence(conf_levels: List[str]) -> str:
    if any(c == "low" for c in conf_levels):
        return "low"
    if any(c == "medium" for c in conf_levels):
        return "medium"
    return "high"


def _legacy_fallback_score(student_answer: str, model_answer: str, max_marks: float) -> EvaluationResult:
    s_vec = embed_text_local(student_answer)
    m_vec = embed_text_local(model_answer)
    sim = max(0.0, cosine_similarity(s_vec, m_vec))
    awarded = round(sim * max_marks, 1)
    rub = int(round(min(float(RUBRIC_SCALE_MAX), sim * float(RUBRIC_SCALE_MAX))))
    return EvaluationResult(
        awarded_marks=awarded,
        max_marks=max_marks,
        rubric_scores=RubricScores(
            factual_accuracy=rub,
            conceptual_completeness=rub,
            reasoning=rub,
            domain_terminology=rub,
            length=rub,
        ),
        feedback="Fallback scoring used due to LLM unavailability.",
        grading_confidence="low",
        flags=["llm_unavailable", "review_required"],
    )


def _infer_length_score(student_answer: str, model_answer: str, current: int) -> int:
    if current > 0:
        return min(RUBRIC_SCALE_MAX, current)
    s_len = len((student_answer or "").strip())
    m_len = max(1, len((model_answer or "").strip()))
    if s_len < 15:
        return 0
    ratio = s_len / m_len
    if s_len >= 400 or ratio >= 1.0:
        return 5
    if s_len >= 200 or ratio >= 0.65:
        return 4
    if s_len >= 100 or ratio >= 0.4:
        return 3
    if s_len >= 50 or ratio >= 0.2:
        return 2
    return 1


def _apply_length_fallback(
    result: EvaluationResult,
    *,
    student_answer: str,
    model_answer: str,
) -> EvaluationResult:
    rs = result.rubric_scores
    length = _infer_length_score(student_answer, model_answer, rs.length)
    if length == rs.length:
        return result
    flags = list(result.flags)
    if "length_inferred" not in flags:
        flags.append("length_inferred")
    return result.model_copy(
        update={
            "rubric_scores": rs.model_copy(update={"length": length}),
            "flags": flags,
        }
    )


def _from_json_payload(
    payload: Dict[str, Any],
    max_marks: float,
    *,
    student_answer: str = "",
    model_answer: str = "",
) -> EvaluationResult:
    payload = dict(payload)
    payload["max_marks"] = max_marks
    payload["awarded_marks"] = min(max(0.0, float(payload.get("awarded_marks", 0.0))), max_marks)
    rs = payload.get("rubric_scores")
    if isinstance(rs, dict):
        payload["rubric_scores"] = RubricScores.model_validate(rs).model_dump()
    result = EvaluationResult.model_validate(payload)
    if student_answer or model_answer:
        result = _apply_length_fallback(
            result, student_answer=student_answer, model_answer=model_answer
        )
    return result


def _parse_llm_json_text(text: str) -> Dict[str, Any]:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def _provider_error_hint(provider: str, exc: Exception) -> str:
    msg = str(exc)
    if provider == "gemini" and "API_KEY_SERVICE_BLOCKED" in msg:
        return (
            "Gemini API key is blocked (API_KEY_SERVICE_BLOCKED). "
            "Fix key restrictions or rely on OpenRouter fallback."
        )
    if "429" in msg or "quota" in msg.lower() or "rate limit" in msg.lower():
        return (
            f"{provider} rate limit / quota exceeded. "
            "Wait for reset, add credits, or switch GRADE_LLM_PROVIDER in .env."
        )
    line = msg.replace("\n", " ").strip()
    return f"{provider} error: {line[:200]}"


def _score_with_gemini(
    *,
    student_answer: str,
    model_answer: str,
    max_marks: float,
    question_text: str,
    subject_domain: str,
    ocr_confidence: float,
    rubric_override: Optional[dict],
    model_id: str,
    api_key: str,
    rag_context: Optional[str] = None,
) -> EvaluationResult:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    role = grading_system_prompt()
    user = build_grading_user_prompt(
        question_text=question_text,
        subject_domain=subject_domain,
        max_marks=max_marks,
        ocr_confidence=ocr_confidence,
        model_answer=model_answer,
        student_answer=student_answer,
        rag_context=rag_context,
        rubric_override=rubric_override,
    )
    full_prompt = f"{role}\n\n{user}"
    gm = genai.GenerativeModel(model_id)
    resp = gm.generate_content(
        full_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )
    raw = (resp.text or "").strip()
    if not raw:
        raise RuntimeError("Gemini returned empty response")
    return _from_json_payload(
        _parse_llm_json_text(raw),
        max_marks,
        student_answer=student_answer,
        model_answer=model_answer,
    )


def _score_with_openrouter(
    *,
    student_answer: str,
    model_answer: str,
    max_marks: float,
    question_text: str,
    subject_domain: str,
    ocr_confidence: float,
    rubric_override: Optional[dict],
    rag_context: Optional[str] = None,
) -> EvaluationResult:
    role = grading_system_prompt()
    user = build_grading_user_prompt(
        question_text=question_text,
        subject_domain=subject_domain,
        max_marks=max_marks,
        ocr_confidence=ocr_confidence,
        model_answer=model_answer,
        student_answer=student_answer,
        rag_context=rag_context,
        rubric_override=rubric_override,
    )
    raw = openrouter_chat(
        messages=[
            {"role": "system", "content": role},
            {"role": "user", "content": user},
        ],
        json_mode=True,
        temperature=0.0,
    )
    return _from_json_payload(
        _parse_llm_json_text(raw),
        max_marks,
        student_answer=student_answer,
        model_answer=model_answer,
    )


def score_answer_llm(
    *,
    student_answer: str,
    model_answer: str,
    max_marks: float,
    question_text: str,
    subject_domain: str,
    ocr_confidence: float,
    rubric_override: Optional[dict] = None,
    rag_context: Optional[str] = None,
) -> tuple[EvaluationResult, str]:
    """
    Return (EvaluationResult, llm_model label).

    Order: mock env → Gemini → OpenRouter (if enabled) → embedding fallback.
    """
    llm_on = os.environ.get("GRADE_ENABLE_LLM", "").lower() in {"1", "true", "yes"}
    if not llm_on:
        return _legacy_fallback_score(student_answer, model_answer, max_marks), "fallback-legacy"

    model_name = gemini_model()

    raw_json = os.environ.get("GRADE_LLM_MOCK_RESPONSE")
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            return _from_json_payload(parsed, max_marks), model_name
        except Exception:
            return _legacy_fallback_score(student_answer, model_answer, max_marks), model_name

    last_error: Optional[Exception] = None
    last_provider = "llm"
    gkey = gemini_api_key()
    if gkey:
        try:
            res = _score_with_gemini(
                student_answer=student_answer,
                model_answer=model_answer,
                max_marks=max_marks,
                question_text=question_text,
                subject_domain=subject_domain,
                ocr_confidence=ocr_confidence,
                rubric_override=rubric_override,
                model_id=model_name,
                api_key=gkey,
                rag_context=rag_context,
            )
            flags = list(res.flags)
            if "gemini_ok" not in flags:
                flags.append("gemini_ok")
            return res.model_copy(update={"flags": flags}), model_name
        except Exception as exc:
            last_error = exc
            last_provider = "gemini"
            logger.warning("Gemini grading failed: %s", exc)

    if openrouter_fallback_enabled():
        or_model = openrouter_model()
        try:
            res = _score_with_openrouter(
                student_answer=student_answer,
                model_answer=model_answer,
                max_marks=max_marks,
                question_text=question_text,
                subject_domain=subject_domain,
                ocr_confidence=ocr_confidence,
                rubric_override=rubric_override,
                rag_context=rag_context,
            )
            flags = list(res.flags)
            flags.append("openrouter_ok")
            if last_error:
                flags.append("gemini_error")
            return res.model_copy(update={"flags": flags}), f"openrouter:{or_model}"
        except Exception as exc:
            last_error = exc
            last_provider = "openrouter"
            logger.warning("OpenRouter grading failed: %s", exc)

    fb = _legacy_fallback_score(student_answer, model_answer, max_marks)
    hints: List[str] = []
    rate_limited = False
    if last_error:
        err_s = str(last_error).lower()
        rate_limited = any(
            token in err_s
            for token in ("429", "quota", "rate limit", "token", "resource_exhausted", "free-models-per")
        )
        hints.append(_provider_error_hint(last_provider, last_error))
    elif not gkey and not openrouter_fallback_enabled():
        hints.append(
            "Set GRADE_GEMINI_API_KEY and/or GRADE_OPENROUTER_API_KEY in .env and restart the API."
        )
    extra_flags = ["gemini_error", "openrouter_error", "review_required"]
    if rate_limited:
        extra_flags.append("llm_rate_limited")
    fb = fb.model_copy(
        update={
            "feedback": f"{fb.feedback} {' '.join(hints)}".strip(),
            "flags": list(dict.fromkeys(list(fb.flags) + extra_flags)),
        }
    )
    return fb, model_name
