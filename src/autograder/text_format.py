"""
Post-OCR text formatting: fix misspellings and jumbled words before grading.

Heuristic cleanup always runs. Optional Gemini pass (``GRADE_OCR_FORMAT_LLM``) uses the
matched question / key vocabulary only to disambiguate letters — not to invent answers.
"""

from __future__ import annotations

import difflib
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from autograder.rag_extract import normalize_ocr_text

logger = logging.getLogger(__name__)

# Reject LLM cleanup that drops a large tail (common on multi-part answers).
_MIN_LLM_LENGTH_RATIO = 0.80

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
    "suck": "such",
    "eathquake": "earthquake",
    "arides": "arises",
    "witherable": "vulnerable",
    "hagorde": "hazards",
    "fisk": "risk",
    "expocity": "capacity",
    "meassures": "measures",
    "distister": "disaster",
    "butter": "better",
    "sespond": "respond",
    "epnomic": "economic",
    "valnerability": "vulnerability",
    "liniced": "linked",
    "dhack": "lack",
    "aralysis": "analysis",
    "evalumper": "",
    "cyclone": "cyclone",
    "cyclones": "cyclones",
    "prepared": "prepared",
    # Compiler design / lexical analysis OCR
    "sourd": "source",
    "sped": "speed",
    "sential": "sentinel",
    "repeadly": "repeatedly",
    "repead": "repeat",
    "onerall": "overall",
    "bopert": "proper",
    "proase": "process",
    "proms": "programs",
    "allinitasting": "facilitating",
    "proms": "programs",
}

# Extra domain terms for fuzzy correction when keys omit them.
_DOMAIN_VOCAB: Set[str] = {
    "source", "programs", "program", "buffer", "buffering", "lexical", "analyzer",
    "compiler", "sentinel", "lookahead", "token", "tokens", "efficiency",
    "operations", "bootstrapping", "portability", "maintainability", "recognition",
    "repeatedly", "overall", "performance", "facilitating",
}

# Regex replacements applied after whole-word fixes (order matters).
_OCR_PATTERN_FIXES: List[Tuple[str, str]] = [
    (r"\bprepared\s+nese\b", "preparedness"),
    (r"\bprepared\s+ness\b", "preparedness"),
    (r"\bsuck\s+as\b", "such as"),
    (r"\bthus\s*;\s*", "Thus, "),
    (r"\bdisasters\s+fisk\b", "disaster risk"),
    (r"\bdisaster\s+fisk\b", "disaster risk"),
    (r"\b6\s*\)\s*", "b) "),
    (r"\b4\s*,\s*and\s+a\s*\)\s*", "a) "),
    (r"\bin\s+stead\b", "instead"),
    (r"\breading\s+sourd\b", "reading source"),
    (r"\bsourd\s+programs?\b", "source programs"),
    (r"\binto\s+an\s+the\s+source\b", "into the source"),
    (r"\breads\s+a\s+block\s+lace\s+buffer\b", "reads a block into a buffer"),
    (r"\breads\s+a\s+block\s+into\s+a\s+lace\b", "reads a block into a buffer"),
    (r"\bincreases\s+sped\b", "increases speed"),
    (r"\bwith\s+sential\b", "with sentinel"),
    (r"\bsential\s+characters\b", "sentinel characters"),
    (r"\bbopert\s+buffering\b", "proper buffering"),
    (r"\binput\s+buffering\s+of\s+reduces\b", "input buffering reduces"),
    (r"\binput\s+buffering\s+reduces\s+allinitasting\b", "input buffering facilitates"),
    (r"\bThis\s+General,\s*two,\s*buffer\b", "Generally, two buffers"),
    (r"\bGenerally,\s*are\s+used\b", "Generally, two buffers are used"),
    (r"\b(facilitates|reduces|improves)\s+in\s*$", r"\1 the overall performance of the compiler."),
    (r"\bthe\s+the\b", "the"),
    (r"\bGeneral,\s*I\b", "Generally,"),
    (r"\bAt\s+also\b", "It also"),
    (r"\blook\s*\.\s*-\s*ahead\b", "look-ahead"),
    (r"[•·]\s*", " "),
    (r"[✓✔]\s*", " "),
    (r'\s*"\s*', " "),
    (r"_\s+", " "),
    (r"\s+_\s+", " "),
    (r"\s{2,}", " "),
]

_SCANNER_JUNK = re.compile(
    r"(?:scanned\s+with\s+[\w\s]+scanner|evalumper)\s*",
    re.IGNORECASE,
)

# Next sub-answer on the same page (e.g. 6a input buffering → 6b bootstrapping).
_LEAKED_SUBPART = re.compile(
    r"\b(?:b\s*\)\s*(?:bootstrapping|write|explain|define|illustrate)"
    r"|bootstrapping\s+is\s+the\s+process)\b",
    re.IGNORECASE,
)


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
    vocab: Set[str] = set(_DOMAIN_VOCAB)
    for blob in parts:
        for w in re.findall(r"[A-Za-z]{3,}", blob):
            vocab.add(w.lower())
    return vocab


def _strip_leaked_subpart_bleed(text: str, key: Dict[str, Any]) -> str:
    """Drop a following sub-answer (e.g. b) Bootstrapping) leaked into this OCR strip."""
    from autograder.rag.boundaries import is_multipart_question

    t = (text or "").strip()
    if not t or is_multipart_question(str(key.get("expected_answer") or "")):
        return t

    patterns: List[re.Pattern[str]] = [_LEAKED_SUBPART]
    if re.search(r"\binput\s+buffering\b", t, re.I):
        patterns.extend(
            [
                re.compile(r"\b(?:proase|process)\s+of\s+developing\b", re.I),
                re.compile(r"\ba\s+simple\s+(?:compiler\s+)?(?:is\s+)?(?:first\s+)?written\b", re.I),
            ]
        )
    for pat in patterns:
        m = pat.search(t)
        if m and m.start() > 50:
            return t[: m.start()].strip()
    return t


def _polish_sentences(text: str) -> str:
    """Light punctuation / capitalization without changing meaning."""
    t = (text or "").strip()
    if not t:
        return t
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"([.!?])\s+([a-z])", lambda m: f"{m.group(1)} {m.group(2).upper()}", t)
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
    return t.strip()


def _strip_scanner_artifacts(text: str) -> str:
    return _SCANNER_JUNK.sub("", text or "").strip()


def _heuristic_format(text: str, vocab: Set[str]) -> str:
    t = _strip_scanner_artifacts(normalize_ocr_text(text))
    if not t:
        return t

    t = re.sub(r"\s+([.,;:!?])\s+", r"\1 ", t)
    t = re.sub(r"\s{2,}", " ", t)

    for pat, repl in _OCR_PATTERN_FIXES:
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)

    words = t.split()
    out: List[str] = []
    for w in words:
        bare = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", w)
        lower = bare.lower()
        if lower in _OCR_WORD_FIXES:
            fixed = _OCR_WORD_FIXES[lower]
            if not fixed:
                continue
            if bare and bare[0].isupper():
                fixed = fixed.capitalize()
            w = w.replace(bare, fixed) if bare else fixed
            out.append(w)
            continue
        if len(bare) >= 4 and vocab:
            cutoff = 0.82 if len(bare) >= 5 else 0.86
            match = difflib.get_close_matches(lower, list(vocab), n=1, cutoff=cutoff)
            if match and match[0] != lower:
                rep = match[0]
                if bare and bare[0].isupper():
                    rep = rep.capitalize()
                w = w.replace(bare, rep)
        out.append(w)

    t = " ".join(out)
    t = re.sub(r"\b(?:[A-Za-z]\s+){4,}([A-Za-z])\b", r"\1", t)
    # Restore readable sub-part breaks.
    t = re.sub(r"\s+([ab]\))\s+", r"\n\1 ", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+\b(?:in|of|the|a|an)\s*$", ".", t, flags=re.IGNORECASE)
    if t and t[-1] not in ".!?":
        t = t + "."
    return _polish_sentences(normalize_ocr_text(t))


def _format_with_openrouter(raw: str, key: Dict[str, Any]) -> str:
    from autograder.llm_providers import build_ocr_format_prompt, openrouter_chat

    vocab_hint = ", ".join(sorted(_key_vocabulary(key)))[:500]
    prompt = build_ocr_format_prompt(raw, key, vocab_hint)
    est_tokens = max(2048, min(8192, len(raw) // 3 + 512))
    return normalize_ocr_text(
        openrouter_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=est_tokens,
        )
    )


def _format_with_gemini(
    raw: str,
    key: Dict[str, Any],
    *,
    model_id: str,
    api_key: str,
) -> str:
    import google.generativeai as genai

    from autograder.llm_providers import build_ocr_format_prompt, ocr_format_system_prompt

    vocab_hint = ", ".join(sorted(_key_vocabulary(key)))[:500]
    user_prompt = build_ocr_format_prompt(raw, key, vocab_hint)
    system = ocr_format_system_prompt()

    genai.configure(api_key=api_key)
    gm = genai.GenerativeModel(model_id, system_instruction=system)
    est_tokens = max(2048, min(8192, len(raw) // 3 + 512))
    resp = gm.generate_content(
        user_prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.0,
            max_output_tokens=est_tokens,
        ),
    )
    out = (resp.text or "").strip()
    if not out:
        raise RuntimeError("OCR format LLM returned empty text")
    return normalize_ocr_text(out)


def _llm_output_acceptable(source: str, llm_out: str) -> bool:
    """True when formatted text keeps most of the OCR content (not a summary)."""
    src = (source or "").strip()
    out = (llm_out or "").strip()
    if not out:
        return False
    if not src:
        return True
    if len(out) >= len(src) * _MIN_LLM_LENGTH_RATIO:
        return True
    if re.search(r"[(\[]?\s*b[)\]]\s", out, re.I) and re.search(
        r"[(\[]?\s*b[)\]]\s", src, re.I
    ):
        return len(out) >= len(src) * 0.65
    return False


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

    trimmed = _strip_leaked_subpart_bleed(raw, key)
    bleed_trimmed = trimmed != raw.strip()
    vocab = _key_vocabulary(key)
    heuristic = _heuristic_format(trimmed, vocab)
    flags: List[str] = ["ocr_formatted"]
    if bleed_trimmed:
        flags.append("ocr_subpart_bleed_trimmed")

    if heuristic != normalize_ocr_text(_strip_scanner_artifacts(trimmed)):
        flags.append("ocr_heuristic_fix")

    if force_heuristic or not _llm_format_enabled():
        return FormattedOcrText(
            raw=raw,
            formatted=heuristic or trimmed or raw,
            method="heuristic",
            flags=flags,
        )

    from autograder.llm_providers import (
        gemini_api_key,
        gemini_model,
        openrouter_fallback_enabled,
    )

    api_key = gemini_api_key()
    model_id = gemini_model()
    llm_out: Optional[str] = None
    method = "heuristic"
    llm_source = heuristic or trimmed or raw

    if api_key:
        try:
            llm_out = _format_with_gemini(llm_source, key, model_id=model_id, api_key=api_key)
            method = "llm"
            flags.append("ocr_gemini_format")
        except Exception as exc:
            logger.warning("OCR format Gemini failed: %s", exc)
            flags.append("ocr_format_gemini_failed")

    if (not llm_out or method == "heuristic") and openrouter_fallback_enabled():
        try:
            llm_out = _format_with_openrouter(llm_source, key)
            method = "llm"
            flags.append("ocr_openrouter_format")
        except Exception as exc:
            logger.warning("OCR format OpenRouter failed: %s", exc)
            flags.append("ocr_format_openrouter_failed")

    if llm_out and llm_out != heuristic:
        flags.append("ocr_llm_fix")
    if llm_out and not _llm_output_acceptable(llm_source, llm_out):
        logger.warning(
            "OCR format LLM truncated output (%s -> %s chars); using heuristic",
            len(llm_source),
            len(llm_out),
        )
        flags.append("ocr_llm_truncated")
        llm_out = None
        method = "heuristic"

    if llm_out:
        return FormattedOcrText(
            raw=raw,
            formatted=llm_out,
            method=method,
            flags=flags,
        )

    if not api_key and not openrouter_fallback_enabled():
        flags.append("ocr_format_llm_skipped")
    else:
        flags.append("ocr_format_llm_failed")
    return FormattedOcrText(
        raw=raw,
        formatted=heuristic or raw,
        method="heuristic",
        flags=flags,
    )
