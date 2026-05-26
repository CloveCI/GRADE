"""
Post-OCR text formatting: fix misspellings and jumbled words before grading.

Heuristic cleanup always runs. Optional Gemini pass (``GRADE_OCR_FORMAT_LLM``) uses the
matched question / key vocabulary only to disambiguate letters — not to invent answers.
"""

from __future__ import annotations

import difflib
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from autograder.rag_extract import normalize_ocr_text

logger = logging.getLogger(__name__)

# Common Vision / scan OCR confusions (whole-word, conservative).
_OCR_WORD_FIXES = {
    "fos": "for",
    "hte": "the",
    "teh": "the",
    "adn": "and",
    "waht": "what",
    "whcih": "which",
    "resrouted": "rerouted",
    "staring": "starting",
    "inline": "in line",
    "slovin": "solving",
    "uit": "unit",
}


@dataclass
class FormattedOcrText:
    raw: str
    formatted: str
    method: str  # heuristic | llm | passthrough
    flags: List[str]


def _llm_format_enabled() -> bool:
    if os.environ.get("GRADE_OCR_FORMAT_LLM", "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False
    if os.environ.get("GRADE_OCR_FORMAT_LLM", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True
    # Default: format with LLM when LLM grading is enabled and a key is present.
    return os.environ.get("GRADE_ENABLE_LLM", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _key_vocabulary(key: Dict[str, Any]) -> Set[str]:
    parts = [
        str(key.get("question_id") or ""),
        str(key.get("expected_answer") or ""),
        str(key.get("domain") or ""),
    ]
    vocab: Set[str] = set()
    for blob in parts:
        for w in re.findall(r"[A-Za-z]{3,}", blob):
            vocab.add(w.lower())
    return vocab


def _heuristic_format(text: str, vocab: Set[str]) -> str:
    t = normalize_ocr_text(text)
    if not t:
        return t

    # Drop isolated punctuation tokens between words.
    t = re.sub(r"\s+([.,;:!?])\s+", r"\1 ", t)
    t = re.sub(r"\s{2,}", " ", t)

    words = t.split()
    out: List[str] = []
    for w in words:
        bare = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", w)
        lower = bare.lower()
        if lower in _OCR_WORD_FIXES:
            fixed = _OCR_WORD_FIXES[lower]
            if bare and bare[0].isupper():
                fixed = fixed.capitalize()
            w = w.replace(bare, fixed) if bare else fixed
            out.append(w)
            continue
        if len(bare) >= 4 and vocab:
            match = difflib.get_close_matches(lower, list(vocab), n=1, cutoff=0.88)
            if match and match[0] != lower:
                rep = match[0]
                if bare[0].isupper():
                    rep = rep.capitalize()
                w = w.replace(bare, rep)
        out.append(w)

    t = " ".join(out)
    # Letter-spaced noise: "a b c" sequences → only merge very short runs
    t = re.sub(r"\b(?:[A-Za-z]\s+){4,}([A-Za-z])\b", r"\1", t)
    return normalize_ocr_text(t)


def _format_with_gemini(
    raw: str,
    key: Dict[str, Any],
    *,
    model_id: str,
    api_key: str,
) -> str:
    import google.generativeai as genai

    qid = str(key.get("question_id") or "")
    expected = str(key.get("expected_answer") or "").strip()
    vocab_hint = ", ".join(sorted(_key_vocabulary(key)))[:500]

    prompt = f"""You fix handwritten exam OCR errors only.

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

    genai.configure(api_key=api_key)
    gm = genai.GenerativeModel(model_id)
    resp = gm.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.0),
    )
    out = (resp.text or "").strip()
    if not out:
        raise RuntimeError("OCR format LLM returned empty text")
    return normalize_ocr_text(out)


def format_student_answer(
    raw_ocr: str,
    key: Dict[str, Any],
    *,
    force_heuristic: bool = False,
) -> FormattedOcrText:
    """
    Turn noisy OCR into readable text for grading and RAG search.

    Returns ``formatted`` text; ``raw`` is preserved for audit/UI.
    """
    raw = raw_ocr or ""
    if not raw.strip():
        return FormattedOcrText(
            raw=raw,
            formatted=raw,
            method="passthrough",
            flags=["ocr_empty"],
        )

    vocab = _key_vocabulary(key)
    heuristic = _heuristic_format(raw, vocab)
    flags: List[str] = ["ocr_formatted"]

    if heuristic != normalize_ocr_text(raw):
        flags.append("ocr_heuristic_fix")

    if force_heuristic or not _llm_format_enabled():
        return FormattedOcrText(
            raw=raw,
            formatted=heuristic or raw,
            method="heuristic",
            flags=flags,
        )

    api_key = os.environ.get("GRADE_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        flags.append("ocr_format_llm_skipped")
        return FormattedOcrText(raw=raw, formatted=heuristic or raw, method="heuristic", flags=flags)

    model_id = os.environ.get("GRADE_LLM_MODEL", "gemini-2.0-flash")
    try:
        llm_out = _format_with_gemini(heuristic or raw, key, model_id=model_id, api_key=api_key)
        if llm_out and llm_out != heuristic:
            flags.append("ocr_llm_fix")
        return FormattedOcrText(
            raw=raw,
            formatted=llm_out or heuristic or raw,
            method="llm",
            flags=flags,
        )
    except Exception as exc:
        logger.warning("OCR format LLM failed, using heuristic only: %s", exc)
        flags.append("ocr_format_llm_failed")
        return FormattedOcrText(
            raw=raw,
            formatted=heuristic or raw,
            method="heuristic",
            flags=flags,
        )
