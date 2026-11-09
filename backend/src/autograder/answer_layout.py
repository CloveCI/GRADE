"""
Automatic answer layout: where each marking-scheme question's answer sits on the sheet, without a preset.

1. OCR every page into positioned lines (PaddleOCR text detection + recognition).
2. Find answer labels written in the ruled left margin ("1st Ans", "2nd Ans", ...) from the ink alone; these are
   hints, because OCR of the label itself is unreliable.
3. Split the lines, in reading order, into one contiguous group per key question with dynamic programming:
   each line prefers the key whose model answer it resembles (character-trigram TF-IDF, robust to OCR misspellings),
   a group start earns a bonus on a labelled line and pays a small penalty elsewhere when the sheet has labels.
4. Turn each group into full-width strips per page (an answer may run across pages).

Checked on the CIE samples: Disaster Mitigation 6/6 boundaries, Data Mining 6/6, DAA 5/6 (one sentence moved
between Q1 and Q2). Used only when the teacher gives no layout. Returns ``None`` when PaddleOCR is unavailable or
there are fewer lines than questions, so the caller can fall back.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

LABEL_BONUS = 1.0      # group starts on a line next to a margin label
MARKER_BONUS = 0.6     # line text starts like "2nd Ans" / "5Ans" with the matching number
START_PENALTY = 0.5    # group starts on an unlabelled line, when the sheet has labels
LINE_WEIGHT_CHARS = 40  # lines shorter than this count proportionally less (little evidence)
PAD = 12

_MARKER = re.compile(r"^\W*(\d{1,2})\s*(?:st|nd|rd|th|n)?\W{0,3}\s*(?:a\s*n\s*s?|an)?\b", re.IGNORECASE)
_NOISE_LINE = re.compile(r"^\W*\d{0,2}\W*$")
_WATERMARK = re.compile(r"scanned with", re.IGNORECASE)


@dataclass
class AutoLayout:
    """Per-question strips found on the sheet."""

    crops: List[np.ndarray]                    # full-width grayscale strips, in question order then page order
    bboxes: List[Tuple[int, int, int, int]]   # (x, y, w, h) on the deskewed page at the evaluation render scale
    pages: List[int]                           # 1-based page of each strip
    groups: List[List[int]]                    # strip indices per question
    regions_per_page: List[int]                # strips per page (diagnostic)
    labels_found: int
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------------------------------- page analysis


def _page_lines(gray: np.ndarray, page: int) -> Optional[List[Dict[str, Any]]]:
    """Positioned OCR lines for one page, or ``None`` when PaddleOCR is not usable."""
    try:
        import paddleocr as paddleocr_module  # type: ignore

        from autograder.ocr import _get_paddle_ocr, _paddle_major_version
    except ImportError:
        return None
    try:
        ocr = _get_paddle_ocr(paddleocr_module)
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        out: List[Dict[str, Any]] = []
        if _paddle_major_version(paddleocr_module) >= 3:
            for res in ocr.predict(bgr) or []:
                for poly, text, score in zip(res.get("dt_polys") or [], res.get("rec_texts") or [], res.get("rec_scores") or []):
                    pts = np.asarray(poly)
                    out.append({"page": page, "y0": int(pts[:, 1].min()), "y1": int(pts[:, 1].max()),
                                "x0": int(pts[:, 0].min()), "text": str(text), "conf": float(score)})
        else:
            for group in ocr.ocr(bgr, cls=True) or []:
                for det in group or []:
                    pts = np.asarray(det[0])
                    out.append({"page": page, "y0": int(pts[:, 1].min()), "y1": int(pts[:, 1].max()),
                                "x0": int(pts[:, 0].min()), "text": str(det[1][0]), "conf": float(det[1][1])})
        return out
    except Exception as e:  # model download / runtime failure -> caller falls back
        logger.warning("auto layout: PaddleOCR line detection failed on page %s: %s", page, e)
        return None


def margin_label_spans(gray: np.ndarray) -> List[Tuple[int, int]]:
    """
    Vertical spans of handwriting left of the ruled margin line (answer labels such as "3rd Ans").

    Dark ink only (rules and scanner speckle are lighter); long horizontal and vertical rules are removed first so a
    label touching a rule is not swallowed by it; remaining strokes are grouped by vertical proximity.
    """
    h, w = gray.shape[:2]
    inv = (gray < 90).astype(np.uint8) * 255
    vert = cv2.morphologyEx(inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 10))))
    lo, hi = int(w * 0.04), int(w * 0.35)
    col = vert[:, lo:hi].sum(axis=0)
    if col.size == 0 or col.max() < 255 * h * 0.05:
        return []  # no ruled margin on this page
    mx = lo + int(np.argmax(col))
    horiz = cv2.morphologyEx(inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 12), 1)))
    vert_short = cv2.morphologyEx(inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 35))))
    rules = cv2.dilate(cv2.bitwise_or(horiz, vert_short), np.ones((3, 3), np.uint8))
    x0 = int(w * 0.02)
    if mx - 8 <= x0 + 10:
        return []
    band = cv2.subtract(inv, rules)[:, x0 : mx - 8]
    n, _, stats, _ = cv2.connectedComponentsWithStats(band, 8)
    strokes = []
    for i in range(1, n):
        _, y, bw, bh, area = (int(v) for v in stats[i])
        if area < 50 or bh < 14 or bh > 260:  # specks, rule fragments, taller than any label
            continue
        if bh > 4 * bw or bw > 6 * bh:          # vertical edge pieces, horizontal rule pieces
            continue
        strokes.append((y, y + bh, area))
    strokes.sort()
    blobs: List[List[int]] = []
    for y0, y1, area in strokes:
        if blobs and y0 <= blobs[-1][1] + 40:
            blobs[-1][1] = max(blobs[-1][1], y1)
            blobs[-1][2] += area
        else:
            blobs.append([y0, y1, area])
    return [(b[0], b[1]) for b in blobs if b[2] >= 500 and b[1] - b[0] >= 35]


def _merge_visual_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Join OCR boxes on the same visual line (margin label + text) and drop page numbers / scanner watermarks."""
    lines = sorted(lines, key=lambda l: (l["page"], l["y0"], l["x0"]))
    merged: List[Dict[str, Any]] = []
    for line in lines:
        if merged and merged[-1]["page"] == line["page"] and abs(merged[-1]["y0"] - line["y0"]) < 25:
            m = merged[-1]
            m["text"] = f"{m['text']} {line['text']}" if line["x0"] >= m["x0"] else f"{line['text']} {m['text']}"
            m["x0"] = min(m["x0"], line["x0"])
            m["y1"] = max(m["y1"], line["y1"])
        else:
            merged.append(dict(line))
    return [l for l in merged if not _NOISE_LINE.match(l["text"].strip()) and not _WATERMARK.search(l["text"])]


# ----------------------------------------------------------------------------------------------- the split


def _trigrams(text: str) -> Counter:
    t = re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", text.lower()))
    return Counter(t[i : i + 3] for i in range(len(t) - 2))


def split_lines_by_key(
    line_texts: Sequence[str],
    key_texts: Sequence[str],
    *,
    labelled: Sequence[bool] = (),
) -> Optional[List[Tuple[int, int]]]:
    """
    Best split of ordered lines into ``len(key_texts)`` contiguous, non-empty groups: ``[(start, end), ...]``,
    end exclusive. ``labelled[i]`` marks lines next to a margin label.
    """
    K, L = len(key_texts), len(line_texts)
    if K < 1 or L < K:
        return None
    key_grams = [_trigrams(t) for t in key_texts]
    df = Counter(g for c in key_grams for g in c)
    idf = {g: math.log((K + 1) / (df[g] + 0.5)) for g in df}

    def vec(c: Counter) -> Dict[str, float]:
        v = {g: n * idf[g] for g, n in c.items() if g in idf}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {g: x / norm for g, x in v.items()}

    key_vecs = [vec(c) for c in key_grams]
    score: List[List[float]] = []
    for text in line_texts:
        lv = vec(_trigrams(text))
        sims = [sum(x * kv.get(g, 0.0) for g, x in lv.items()) for kv in key_vecs]
        mean = sum(sims) / K
        weight = min(1.0, len(text) / LINE_WEIGHT_CHARS)
        score.append([weight * (s - mean) for s in sims])

    any_label = any(labelled)

    def start_bonus(i: int, k: int) -> float:
        m = _MARKER.match(line_texts[i])
        b = MARKER_BONUS if (m and int(m.group(1)) == k + 1) else 0.0
        if i < len(labelled) and labelled[i]:
            return b + LABEL_BONUS
        return b - (START_PENALTY if any_label and i > 0 else 0.0)

    prefix = [[0.0] * (L + 1) for _ in range(K)]
    for k in range(K):
        for i in range(L):
            prefix[k][i + 1] = prefix[k][i] + score[i][k]
    neg = float("-inf")
    best = [[neg] * (L + 1) for _ in range(K + 1)]
    back = [[0] * (L + 1) for _ in range(K + 1)]
    best[0][0] = 0.0
    for k in range(1, K + 1):
        for j in range(k, L - (K - k) + 1):
            for i in range(k - 1, j):
                if best[k - 1][i] == neg:
                    continue
                v = best[k - 1][i] + prefix[k - 1][j] - prefix[k - 1][i] + start_bonus(i, k - 1)
                if v > best[k][j]:
                    best[k][j], back[k][j] = v, i
    if best[K][L] == neg:
        return None
    cuts: List[Tuple[int, int]] = []
    j = L
    for k in range(K, 0, -1):
        i = back[k][j]
        cuts.append((i, j))
        j = i
    return list(reversed(cuts))


# ----------------------------------------------------------------------------------------------- whole sheet


def detect_answer_layout(
    page_grays: Sequence[np.ndarray],
    key_texts: Sequence[str],
) -> Optional[AutoLayout]:
    """Find one region per key question across deskewed page images. ``None`` when it cannot be done."""
    if len(key_texts) < 2 or not page_grays:
        return None
    raw_lines: List[Dict[str, Any]] = []
    label_spans: Dict[int, List[Tuple[int, int]]] = {}
    for p, gray in enumerate(page_grays, start=1):
        lines = _page_lines(gray, p)
        if lines is None:
            return None
        raw_lines.extend(lines)
        label_spans[p] = margin_label_spans(gray)
    lines = _merge_visual_lines(raw_lines)
    if len(lines) < len(key_texts):
        return None

    # each label marks exactly one line: the one closest to its centre
    labelled = [False] * len(lines)
    for page, spans in label_spans.items():
        for y0, y1 in spans:
            cy = (y0 + y1) / 2
            cands = [(abs((l["y0"] + l["y1"]) / 2 - cy), i) for i, l in enumerate(lines)
                     if l["page"] == page and l["y0"] <= y1 + 20 and l["y1"] >= y0 - 20]
            if cands:
                labelled[min(cands)[1]] = True

    cuts = split_lines_by_key([l["text"] for l in lines], key_texts, labelled=labelled)
    if not cuts:
        return None

    # geometry: a question's strip on a page runs from its first line (or the page's first line, when it continues
    # from the previous page) down to just above the next question's first line on that page (or the last line)
    q_of_line = [0] * len(lines)
    for q, (i, j) in enumerate(cuts):
        for n in range(i, j):
            q_of_line[n] = q
    crops: List[np.ndarray] = []
    bboxes: List[Tuple[int, int, int, int]] = []
    pages: List[int] = []
    groups: List[List[int]] = [[] for _ in cuts]
    per_page = [0] * len(page_grays)
    for p, gray in enumerate(page_grays, start=1):
        h, w = gray.shape[:2]
        page_idx = [n for n, l in enumerate(lines) if l["page"] == p]
        if not page_idx:
            continue
        top_of_page = max(0, min(lines[n]["y0"] for n in page_idx) - PAD)
        bottom_of_page = min(h, max(lines[n]["y1"] for n in page_idx) + PAD)
        qs = sorted({q_of_line[n] for n in page_idx})
        firsts = {q: min(lines[n]["y0"] for n in page_idx if q_of_line[n] == q) for q in qs}
        for pos, q in enumerate(qs):
            y0 = top_of_page if pos == 0 else max(0, firsts[q] - PAD)
            y1 = max(0, firsts[qs[pos + 1]] - PAD) if pos + 1 < len(qs) else bottom_of_page
            if y1 - y0 < 20:
                continue
            groups[q].append(len(crops))
            crops.append(gray[y0:y1, :])
            bboxes.append((0, y0, w, y1 - y0))
            pages.append(p)
            per_page[p - 1] += 1
    if any(not g for g in groups):
        return None
    return AutoLayout(
        crops=crops,
        bboxes=bboxes,
        pages=pages,
        groups=groups,
        regions_per_page=per_page,
        labels_found=sum(labelled),
        diagnostics={
            "method": "key_text_dp",
            "lines": len(lines),
            "labels_found": sum(labelled),
            "question_first_lines": [lines[i]["text"][:60] for i, _ in cuts],
        },
    )
