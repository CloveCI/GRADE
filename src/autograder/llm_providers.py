"""
LLM providers for grading and OCR cleanup: Gemini (primary) and OpenRouter (fallback).

OpenRouter: https://openrouter.ai/docs/api/reference/overview
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "grading_v2.txt"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def gemini_api_key() -> Optional[str]:
    k = os.environ.get("GRADE_GEMINI_API_KEY", "").strip() or os.environ.get(
        "GEMINI_API_KEY", ""
    ).strip()
    return k or None


def openrouter_api_key() -> Optional[str]:
    k = os.environ.get("GRADE_OPENROUTER_API_KEY", "").strip() or os.environ.get(
        "OPENROUTER_API_KEY", ""
    ).strip()
    return k or None


def openrouter_model() -> str:
    return (
        os.environ.get("GRADE_OPENROUTER_MODEL", "").strip()
        or "google/gemini-2.5-flash-lite"
    )


def gemini_model() -> str:
    return os.environ.get("GRADE_LLM_MODEL", "gemini-2.0-flash")


def openrouter_fallback_enabled() -> bool:
    if not openrouter_api_key():
        return False
    return _env_bool("GRADE_OPENROUTER_FALLBACK", True)


def grading_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else ""


def build_grading_user_prompt(
    *,
    question_text: str,
    subject_domain: str,
    max_marks: float,
    ocr_confidence: float,
    model_answer: str,
    student_answer: str,
    rag_context: Optional[str],
    rubric_override: Optional[dict],
) -> str:
    payload_hint = (
        "Return ONLY JSON with keys: "
        "awarded_marks (number), rubric_scores (object with factual_accuracy, "
        "conceptual_completeness, reasoning, domain_terminology — each integer 0–4), "
        "feedback (string), grading_confidence (exactly one of: high, medium, low), "
        "flags (array of strings). "
        "Do not include max_marks."
    )
    grounding = rag_context if rag_context else (
        f"=== KEY SIDE — Question {question_text} ===\n"
        f"Official model answer: {model_answer}\n\n"
        f"=== STUDENT SIDE — Question {question_text} ===\n"
        f"OCR text: {student_answer}\n"
        "(No RAG excerpts retrieved.)"
    )
    return f"""{payload_hint}

Question ID: {question_text}
Subject domain: {subject_domain}
Max marks for this question: {max_marks}
OCR confidence (0–1): {ocr_confidence:.2f}

Evidence (use ONLY this block; compare KEY SIDE vs STUDENT SIDE semantically):
{grounding}

Rubric override (JSON, or null): {json.dumps(rubric_override) if rubric_override else "null"}
"""


def build_ocr_format_prompt(raw: str, key: Dict[str, Any], vocab_hint: str) -> str:
    qid = str(key.get("question_id") or "")
    expected = str(key.get("expected_answer") or "").strip()
    return f"""You fix handwritten exam OCR errors only.

Rules:
- Output ONLY the corrected student handwriting as plain text (no JSON, no quotes).
- Fix misspellings, broken words, and jumbled word order when clearly caused by OCR.
- Do NOT copy sentences from the reference answer.
- Do NOT add new facts or ideas the student did not attempt.
- Preserve the student's meaning; if unsure, keep the original wording.
- Use reference vocabulary only to spell domain terms correctly.

Question: {qid}
Reference answer (vocabulary hints only, NOT to copy): {expected[:800]}
Domain terms: {vocab_hint or "(none)"}

Raw OCR:
{raw}

Corrected student text:"""


def openrouter_chat(
    *,
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.0,
    json_mode: bool = False,
    max_tokens: int = 4096,
) -> str:
    """Call OpenRouter chat completions; returns assistant message content."""
    api_key = openrouter_api_key()
    if not api_key:
        raise RuntimeError("GRADE_OPENROUTER_API_KEY is not set")

    model_id = model or openrouter_model()
    body: Dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    site = os.environ.get("GRADE_OPENROUTER_HTTP_REFERER", "").strip()
    title = os.environ.get("GRADE_OPENROUTER_APP_TITLE", "GRADE Autograder").strip()
    if site:
        headers["HTTP-Referer"] = site
    if title:
        headers["X-Title"] = title

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenRouter HTTP {e.code}: {detail}") from e

    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter returned no choices")
    message = choices[0].get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        raise RuntimeError("OpenRouter returned empty content")
    return text


def probe_openrouter_live() -> Dict[str, Any]:
    model_id = openrouter_model()
    if not openrouter_api_key():
        return {"ok": False, "model": model_id, "error": "no_api_key"}
    try:
        text = openrouter_chat(
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            model=model_id,
            temperature=0.0,
            max_tokens=16,
        )
        return {"ok": bool(text), "model": model_id, "reply": text[:80]}
    except Exception as exc:
        return {"ok": False, "model": model_id, "error": str(exc)[:500]}


def probe_gemini_live() -> Dict[str, Any]:
    api_key = gemini_api_key()
    model_id = gemini_model()
    if not api_key:
        return {"ok": False, "model": model_id, "error": "no_api_key"}
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        gm = genai.GenerativeModel(model_id)
        resp = gm.generate_content(
            "Reply with exactly: OK",
            generation_config=genai.GenerationConfig(temperature=0.0),
        )
        text = (resp.text or "").strip()
        return {"ok": bool(text), "model": model_id, "reply": text[:80]}
    except Exception as exc:
        return {"ok": False, "model": model_id, "error": str(exc)[:500]}


def llm_status() -> Dict[str, Any]:
    """Aggregate LLM readiness for /api/integrations."""
    llm_on = _env_bool("GRADE_ENABLE_LLM", False)
    gem_key = bool(gemini_api_key())
    or_key = bool(openrouter_api_key())
    gem_probe = probe_gemini_live() if llm_on and gem_key else None
    or_probe = probe_openrouter_live() if llm_on and or_key else None
    gem_ok = bool(gem_probe and gem_probe.get("ok"))
    or_ok = bool(or_probe and or_probe.get("ok"))
    fallback_on = openrouter_fallback_enabled()
    ready = llm_on and (gem_ok or (fallback_on and or_ok))
    return {
        "GRADE_ENABLE_LLM": llm_on,
        "ready": ready,
        "primary": "gemini",
        "fallback": "openrouter" if fallback_on else None,
        "llm_gemini": {
            "GRADE_ENABLE_LLM": llm_on,
            "api_key_present": gem_key,
            "ready": gem_ok,
            "live_probe": gem_probe,
        },
        "llm_openrouter": {
            "api_key_present": or_key,
            "fallback_enabled": fallback_on,
            "ready": or_ok,
            "live_probe": or_probe,
            "model": openrouter_model(),
        },
    }
