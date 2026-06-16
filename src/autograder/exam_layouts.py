"""
CIE-style answer sheet layouts: horizontal OCR strips per PDF page.

Used by API upload/evaluate, RAG ingest, and CLI test scripts.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# exam_id (lowercase) -> rows per PDF page.
EXAM_REGIONS_PER_PAGE: dict[str, List[int]] = {
    # P1=Q1–Q3, P2=Q4a, P3=Q4b+Q5, P4=Q6 (Q4 spans pages 2–3).
    "cie-daa": [3, 1, 2, 1],
    # DATA MINING.pdf: P1=Q1+Q2, P2=Q3+Q4a, P3=Q4b, P4=Q5, P5=Q6 (7 raw strips → 6 keys).
    "cie-dm": [2, 2, 1, 1, 1],
}

DEFAULT_SIX_QUESTION_LAYOUT: List[int] = [3, 1, 2, 1]

# exam_id aliases → preset id for sheet segmentation (independent of key count in DB).
EXAM_LAYOUT_ALIASES: dict[str, str] = {
    "daa": "cie-daa",
    "daa1": "cie-daa",
}

# exam_id -> groups of raw 0-based region indices merged into each answer key (in key order).
EXAM_KEY_REGION_GROUPS: dict[str, List[List[int]]] = {
    "cie-daa": [[0], [1], [2], [3, 4], [5], [6]],
    "cie-dm": [[0], [1], [2], [3, 4], [5], [6]],
}

# Frontend display hints (comma-separated spec strings).
EXAM_REGION_HINTS: dict[str, str] = {
    exam_id: ",".join(str(n) for n in layout)
    for exam_id, layout in EXAM_REGIONS_PER_PAGE.items()
}


def parse_regions_per_page(spec: str | None) -> Optional[List[int]]:
    """Parse ``3,1,1,1`` into ``[3, 1, 1, 1]``."""
    if not spec or not str(spec).strip():
        return None
    parts: List[int] = []
    for piece in str(spec).split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            n = int(piece)
        except ValueError:
            return None
        if n < 1:
            return None
        parts.append(n)
    return parts or None


def infer_layout_for_key_count(num_keys: int) -> Optional[List[int]]:
    """Heuristic layout when no exam preset matches (raw strips must equal key count)."""
    n = int(num_keys or 0)
    if n == 6:
        return list(DEFAULT_SIX_QUESTION_LAYOUT)
    return None


def sheet_layout_preset(exam_id: str) -> Optional[List[int]]:
    """CIE-style row layout for an exam id (aliases included), or None."""
    ex = (exam_id or "").strip().lower()
    if ex in EXAM_REGIONS_PER_PAGE:
        return list(EXAM_REGIONS_PER_PAGE[ex])
    alias = EXAM_LAYOUT_ALIASES.get(ex)
    if alias and alias in EXAM_REGIONS_PER_PAGE:
        return list(EXAM_REGIONS_PER_PAGE[alias])
    if "daa" in ex and "dm" not in ex and "mining" not in ex:
        return list(EXAM_REGIONS_PER_PAGE["cie-daa"])
    return None


def key_region_groups(exam_id: str, num_keys: int = 0) -> Optional[List[List[int]]]:
    """Return raw OCR region index groups per answer key, or None for 1:1."""
    ex = (exam_id or "").strip().lower()
    candidates: List[str] = []
    for cand in (ex, EXAM_LAYOUT_ALIASES.get(ex, "")):
        if cand and cand not in candidates:
            candidates.append(cand)
    preset = sheet_layout_preset(ex)
    if preset:
        for preset_id, layout in EXAM_REGIONS_PER_PAGE.items():
            if list(layout) == list(preset) and preset_id not in candidates:
                candidates.append(preset_id)

    for cand in candidates:
        groups = EXAM_KEY_REGION_GROUPS.get(cand)
        if not groups:
            continue
        if num_keys and len(groups) != num_keys:
            continue
        return [list(g) for g in groups]
    return None


def resolve_regions_per_page(
    exam_id: str,
    *,
    regions_per_page: Optional[List[int]] = None,
    num_keys: int = 0,
) -> Optional[List[int]]:
    """Pick layout from explicit request, exam preset, or 6-question default."""
    ex = (exam_id or "").strip().lower()
    groups = key_region_groups(ex, num_keys) if num_keys else None

    def _layout_ok(layout: List[int]) -> bool:
        if not layout:
            return False
        raw = sum(layout)
        if groups:
            return not num_keys or len(groups) == num_keys
        return not num_keys or raw == num_keys

    if regions_per_page:
        layout = [int(n) for n in regions_per_page if int(n) > 0]
        if layout:
            return layout
    preset = sheet_layout_preset(ex)
    if preset:
        return preset
    inferred = infer_layout_for_key_count(num_keys)
    if inferred and _layout_ok(inferred):
        return inferred
    if num_keys == 6 and not groups:
        return list(DEFAULT_SIX_QUESTION_LAYOUT)
    return None


def page_for_region_index(region_index: int, regions_per_page: List[int]) -> int:
    """Map 0-based answer-key region index to 1-based PDF page."""
    if not regions_per_page:
        return 1
    remaining = int(region_index)
    for page_i, count in enumerate(regions_per_page):
        c = int(count)
        if c < 1:
            continue
        if remaining < c:
            return page_i + 1
        remaining -= c
    return len(regions_per_page)


def page_for_raw_region_index(
    raw_region_index: int,
    regions_per_page: List[int],
    *,
    exam_id: str = "",
    num_keys: int = 0,
) -> int:
    """Map raw OCR strip index to PDF page (accounts for merged keys on multi-strip pages)."""
    groups = key_region_groups(exam_id, num_keys)
    if groups:
        for gi, grp in enumerate(groups):
            if raw_region_index in grp:
                return page_for_region_index(gi, regions_per_page)
    return page_for_region_index(raw_region_index, regions_per_page)


def prompt_from_expected_answer(text: str) -> str:
    import re

    t = (text or "").strip()
    if not t:
        return ""
    m = re.search(r"\bmodel answer\b", t, re.I)
    if m and m.start() > 0:
        t = t[: m.start()].strip()
    stem = re.split(r"\n\s*\n", t, maxsplit=1)[0]
    stem = re.sub(r"\s+", " ", stem.replace("\n", " ")).strip()
    verb = re.search(
        r"\b(Briefly|Discuss|List|Explain|Define|State|Calculate|Describe|Compare|What|How|Write)\b",
        stem,
        re.I,
    )
    if verb and verb.start() > 0:
        stem = stem[verb.start() :].strip()
    return stem
