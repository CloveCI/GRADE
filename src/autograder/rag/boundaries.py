"""
Assemble complete per-question / per-region answers from all RAG chunks with explicit boundaries.

Prevents cross-question overlap by scoping:
  - **Key corpus** → ``question_id`` + ``answer_key_chunks`` char spans
  - **Sheet corpus** → ``region_id`` OCR patch + chunk char spans
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from autograder.db import get_rag_chunks_for_sheet, list_rag_chunks_for_corpus
from autograder.embeddings import cosine_similarity, embed_text_local
from autograder.rag.ingest import keys_document_id, sheet_document_id
from autograder.rag.similarity import apply_similarity_temperature
from autograder.rag_extract import normalize_ocr_text

_KEY_PREFIX = re.compile(
    r"^Question\s+\S+\.\s*(?:Model answer(?:\s+excerpt)?:\s*)?",
    re.IGNORECASE,
)
_MARKS = re.compile(r"\(\d+(?:\.\d+)?\s*marks?\)", re.IGNORECASE)
_QUESTION_BLEED = re.compile(
    r"^(?:Write|Define|State|Explain|Calculate|Discuss|List|Describe|Compare|What|How|Briefly)\b",
    re.IGNORECASE,
)
_ANS_MARKER = re.compile(
    r"\b\d{1,2}\s*(?:st|nd|rd|th)?\s*ans\)?",
    re.IGNORECASE,
)
_Q_LABEL = re.compile(r"\b\d{1,2}\s*\.?\s*q\)?\b", re.IGNORECASE)


@dataclass
class ChunkSpan:
    chunk_id: str
    chunk_index: int
    char_start: Optional[int]
    char_end: Optional[int]
    text: str
    similarity_to_student: Optional[float] = None


@dataclass
class BoundedCorpus:
    corpus: str  # answer_key | sheet
    question_id: str
    region_id: Optional[str]
    start_marker: str
    end_marker: str
    chunk_spans: List[ChunkSpan] = field(default_factory=list)
    assembled_text: str = ""
    question_prompt: str = ""
    answer_text: str = ""


@dataclass
class BoundedEvaluation:
    question_id: str
    region_id: str
    region_index: int
    max_marks: float
    key: BoundedCorpus
    sheet_raw: BoundedCorpus
    sheet_formatted: str
    format_method: str
    similarity_raw: float
    similarity_score: float
    awarded_marks: float
    sheet_answer_start: Optional[int] = None
    sheet_answer_end: Optional[int] = None
    chunk_alignments: List[Dict[str, Any]] = field(default_factory=list)


def _is_subpart_line(text: str) -> bool:
    """``(a)``, ``(b)``, ``a)``, etc. — sub-part inside one question, not the next question."""
    return bool(re.match(r"^[(\[]?[a-z][)\]]\s", (text or "").strip(), re.IGNORECASE))


def is_multipart_question(expected: str) -> bool:
    """True when one question has both (a) and (b) stems or answer sections."""
    text = (expected or "").strip()
    if not text:
        return False
    prompt, model = split_key_expected_answer(text)
    blob = f"{prompt}\n{model}".lower()
    has_a = bool(re.search(r"(?:^|\s)[(\[]?a[)\]]\s", blob))
    has_b = bool(re.search(r"(?:^|\s)[(\[]?b[)\]]\s", blob))
    return has_a and has_b


def _trim_model_bleed(model: str) -> str:
    """Drop a trailing next-question stem accidentally merged into the model answer."""
    text = (model or "").strip()
    if not text:
        return ""
    parts = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]
    while (
        len(parts) >= 2
        and _QUESTION_BLEED.match(parts[-1])
        and not _is_subpart_line(parts[-1])
    ):
        parts.pop()
    mm = _MARKS.search(text)
    if mm and mm.start() > 0:
        text = text[: mm.start()].strip()
        parts = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]
    return " ".join(parts).strip() if parts else text


def _model_char_bounds(expected: str) -> Tuple[str, str, str, int, int]:
    """
    Return (normalized_full, prompt, trimmed_model, char_start, char_end) for answer boundaries.
    """
    normalized = normalize_ocr_text(expected)
    prompt, model = split_key_expected_answer(normalized)
    model = _trim_model_bleed(model)
    if not model:
        return normalized, prompt, "", 0, len(normalized)
    # Keep entire post-prompt body when (a)+(b) share one answer block.
    if is_multipart_question(expected) and "\n\n" in normalized:
        model_start = normalized.find("\n\n") + 2
        model = normalized[model_start:].strip()
        model = _trim_model_bleed(model)
        model_end = model_start + len(model)
        return normalized, prompt, model, model_start, model_end
    model_start = normalized.find(model)
    if model_start < 0 and prompt:
        model_start = len(prompt) + 2 if "\n\n" in normalized else len(prompt) + 1
    if model_start < 0:
        model_start = 0
    model_end = model_start + len(model)
    return normalized, prompt, model, model_start, model_end


def split_key_expected_answer(expected: str) -> Tuple[str, str]:
    """CIE keys store ``question stem`` + blank line + ``model answer``."""
    text = (expected or "").strip()
    if not text:
        return "", ""
    parts = text.split("\n\n", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", text


def _parse_meta(meta: Any) -> Dict[str, Any]:
    if isinstance(meta, dict):
        return meta
    return {}


def _strip_key_wrapper(text: str) -> str:
    return _KEY_PREFIX.sub("", (text or "").strip()).strip()


def _merge_overlap(prev: str, nxt: str, *, max_overlap: int = 200) -> str:
    """Join consecutive chunk texts, dropping duplicated overlap."""
    if not prev:
        return nxt
    if not nxt:
        return prev
    best = 0
    limit = min(len(prev), len(nxt), max_overlap)
    for k in range(limit, 0, -1):
        if prev[-k:] == nxt[:k]:
            best = k
            break
    return prev + nxt[best:]


def assemble_from_spans(
    source_text: str,
    spans: List[ChunkSpan],
) -> str:
    """
    Reconstruct full answer from char spans against ``source_text`` (no overlap duplication).
    Falls back to ordered chunk merge when spans lack positions.
    """
    positioned = [s for s in spans if s.char_start is not None and s.char_end is not None]
    if positioned and source_text:
        c0 = min(s.char_start for s in positioned if s.char_start is not None)
        c1 = max(s.char_end for s in positioned if s.char_end is not None)
        c0 = max(0, int(c0))
        c1 = min(len(source_text), int(c1))
        if c1 > c0:
            return source_text[c0:c1].strip()
    acc = ""
    for s in sorted(spans, key=lambda x: (x.char_start if x.char_start is not None else 10**9, x.chunk_index)):
        piece = s.text.strip()
        if not piece:
            continue
        acc = _merge_overlap(acc, piece)
    return acc.strip()


def _chunks_for_key_question(
    exam_id: str,
    key: Dict[str, Any],
) -> List[Dict[str, Any]]:
    qid = str(key.get("question_id") or "")
    kid = str(key.get("id") or "")
    stored = key.get("answer_chunks") or []
    if stored:
        out: List[Dict[str, Any]] = []
        for ch in stored:
            out.append(
                {
                    "chunk_id": f"key_{ch.get('chunk_id')}",
                    "chunk_index": int(ch.get("chunk_index") or 0),
                    "text_content": str(ch.get("text_content") or ""),
                    "meta": {
                        "kind": "answer_key",
                        "question_id": qid,
                        "key_id": kid,
                        "answer_chunk_index": int(ch.get("chunk_index") or 0),
                        "char_start": ch.get("char_start"),
                        "char_end": ch.get("char_end"),
                    },
                }
            )
        return out
    doc = keys_document_id(exam_id)
    rows = list_rag_chunks_for_corpus(doc, question_id=qid, key_id=kid)
    if rows:
        return rows
    out = []
    for ch in key.get("answer_chunks") or []:
        out.append(
            {
                "chunk_id": f"key_{ch.get('chunk_id')}",
                "chunk_index": int(ch.get("chunk_index") or 0),
                "text_content": str(ch.get("text_content") or ""),
                "meta": {
                    "kind": "answer_key",
                    "question_id": qid,
                    "key_id": kid,
                    "answer_chunk_index": int(ch.get("chunk_index") or 0),
                    "char_start": ch.get("char_start"),
                    "char_end": ch.get("char_end"),
                },
            }
        )
    return out


def _prompt_keywords(prompt: str, *, limit: int = 6) -> List[str]:
    words = re.findall(r"[A-Za-z]{4,}", (prompt or "").lower())
    seen: List[str] = []
    for w in words:
        if w not in seen:
            seen.append(w)
        if len(seen) >= limit:
            break
    return seen


def _best_keyword_anchor(text: str, keywords: List[str], *, after: int = 0) -> Optional[int]:
    """Find earliest position in ``text`` where several question keywords cluster."""
    if not text or not keywords:
        return None
    lower = text.lower()
    hits: List[int] = []
    for kw in keywords:
        pos = lower.find(kw, after)
        if pos >= 0:
            hits.append(pos)
    if not hits:
        return None
    return min(hits)


def _question_number(key: Dict[str, Any]) -> Optional[str]:
    qid = str(key.get("question_id") or "")
    m = re.search(r"\d+", qid)
    return m.group(0) if m else None


def _anchor_start_for_answer(
    normalized: str,
    start: int,
    key: Dict[str, Any],
    *,
    prev_key: Optional[Dict[str, Any]] = None,
) -> int:
    """Skip bleed from a prior question at the top of an isolated OCR strip."""
    qn = _question_number(key)
    search = normalized[start : start + 320]
    anchors: List[int] = []

    if qn:
        for pat in (
            rf"\b{qn}\s*[).:\-]?\s*(?:Ans|ANS)?\b",
            rf"\b{qn}\s*\)\s*[aA]\)",
            rf"\b{qn}\s*\.\s*",
        ):
            m = re.search(pat, search, re.I)
            if m:
                anchors.append(start + m.start())

    expected = str(key.get("expected_answer") or "")
    prompt, _ = split_key_expected_answer(expected)
    for kw in _prompt_keywords(prompt)[:6]:
        if len(kw) < 5:
            continue
        m = re.search(re.escape(kw), search, re.I)
        if m:
            anchors.append(start + m.start())

    m = _QUESTION_BLEED.search(search)
    if m:
        anchors.append(start + m.start())

    if anchors:
        return max(start, min(anchors))

    if prev_key:
        prev_text = str(prev_key.get("expected_answer") or "").lower()
        head = normalized[start : start + 280].lower()
        if any(t in prev_text for t in ("union", "weighted", "find operation")):
            for phrase in (
                "weighted union",
                "weighted curion",
                "union and find",
                "simple union",
                "simple cition",
            ):
                pos = head.find(phrase)
                if pos >= 0:
                    after = normalized.find(".", start + pos)
                    if after > start:
                        start = after + 1
                    break
    return start


def extract_sheet_answer_span(
    region_ocr: str,
    key: Dict[str, Any],
    next_key: Optional[Dict[str, Any]] = None,
    *,
    isolated_region: bool = False,
    prev_key: Optional[Dict[str, Any]] = None,
) -> Tuple[int, int, str]:
    """
    Locate student-answer char boundaries inside a (possibly multi-question) OCR region.

    When ``isolated_region`` is True (one OCR strip per answer key), only trim local
    question/answer labels — do not cut at the next question's keywords.
    """
    normalized = normalize_ocr_text(region_ocr)
    if not normalized:
        return 0, 0, ""

    expected = str(key.get("expected_answer") or "")
    prompt, _ = split_key_expected_answer(expected)
    kws = _prompt_keywords(prompt)

    start = 0
    if isolated_region:
        ans_m = _ANS_MARKER.search(normalized)
        if ans_m and ans_m.start() < 120:
            start = ans_m.end()
        if prompt:
            pl = re.sub(r"\s+", " ", prompt.lower()).strip()
            head = normalized.lower()[: min(220, len(normalized))]
            pos = head.find(pl[: min(48, len(pl))])
            if pos >= 0 and pos < 160:
                start = max(start, pos + len(pl[: min(48, len(pl))]))
        start = _anchor_start_for_answer(normalized, start, key, prev_key=prev_key)
    else:
        ans_m = _ANS_MARKER.search(normalized)
        if ans_m and ans_m.start() < 140:
            start = ans_m.end()
        else:
            start = _best_keyword_anchor(normalized, kws) or 0
        ans_m2 = _ANS_MARKER.search(normalized, max(0, start - 40))
        if ans_m2 and ans_m2.start() >= start - 40:
            start = ans_m2.end()

    if not isolated_region:
        if prompt:
            pl = prompt.lower()
            pos = normalized.lower().find(pl[: min(48, len(pl))], 0, min(len(normalized), start + 120))
            if pos >= 0 and pos <= start + 80:
                start = max(start, pos + len(pl))

    end = len(normalized)
    if next_key:
        next_expected = str(next_key.get("expected_answer") or "")
        next_prompt, _ = split_key_expected_answer(next_expected)
        next_kws = _prompt_keywords(next_prompt)
        nxt = _best_keyword_anchor(normalized, next_kws, after=start + 30)
        if nxt is not None and nxt > start + 40:
            end = min(end, nxt)
        for m in _ANS_MARKER.finditer(normalized, start + 40):
            if m.start() > start + 40:
                end = min(end, m.start())
                break

    extracted = normalized[start:end].strip()
    # Drop a leading repeated question stem (common when strip includes printed question text).
    if prompt:
        pl = re.sub(r"\s+", " ", prompt.lower()).strip()
        el = re.sub(r"\s+", " ", extracted.lower()).strip()
        if el.startswith(pl[: min(len(pl), 60)]):
            extracted = extracted[len(pl) :].lstrip(" .:)-")
    if len(extracted) < 40 and normalized.strip():
        return 0, len(normalized), normalized.strip()
    return start, end, extracted


def assemble_region_text_from_chunks(chunks: List[Dict[str, Any]], region_id: str) -> str:
    """Merge all RAG chunk texts for one sheet ``region_id`` into full OCR."""
    spans: List[ChunkSpan] = []
    for row in sorted(chunks, key=lambda r: int(r.get("chunk_index") or 0)):
        meta = _parse_meta(row.get("meta"))
        if str(meta.get("region_id") or "") != region_id:
            continue
        spans.append(
            ChunkSpan(
                chunk_id=str(row.get("chunk_id") or ""),
                chunk_index=int(row.get("chunk_index") or 0),
                char_start=_int_or_none(meta.get("char_start")),
                char_end=_int_or_none(meta.get("char_end")),
                text=str(row.get("text_content") or ""),
            )
        )
    return assemble_from_spans("", spans)


def _region_sort_key(region_id: str) -> Tuple[int, int, str]:
    rid = (region_id or "").strip()
    m = re.match(r"^P(\d+)_R(\d+)$", rid, re.IGNORECASE)
    if m:
        return (int(m.group(1)), int(m.group(2)), rid)
    m2 = re.match(r"^R(\d+)$", rid, re.IGNORECASE)
    if m2:
        return (1, int(m2.group(1)), rid)
    return (9999, 9999, rid)


def sort_regions(regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Order sheet regions top-to-bottom: P1_R1, P1_R2, … P2_R1, …"""
    nonempty = [r for r in regions if str(r.get("text") or "").strip()]
    return sorted(
        nonempty,
        key=lambda r: _region_sort_key(str(r.get("region_id") or "")),
    )


def pair_keys_with_regions(
    keys: List[Dict[str, Any]],
    regions: List[Dict[str, Any]],
    *,
    regions_per_page: Optional[List[int]] = None,
) -> List[Tuple[Dict[str, Any], Dict[str, Any], int, bool]]:
    """
    Map each answer key to one sheet region.

    Returns ``(key, region, region_index, one_to_one)`` tuples.
    When ``one_to_one`` is True the whole OCR patch is the student answer (no in-region trim).
    """
    ordered = sorted(keys, key=lambda k: int(k.get("sort_order") or 0))
    regs = sort_regions(regions)
    if not ordered or not regs:
        return []

    def _zip_positional(reg_list: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any], int, bool]]:
        n = min(len(ordered), len(reg_list))
        return [(ordered[i], reg_list[i], i, True) for i in range(n)]

    if len(regs) == len(ordered):
        return _zip_positional(regs)

    if regions_per_page and sum(regions_per_page) == len(ordered):
        by_page: Dict[int, List[Dict[str, Any]]] = {}
        for r in regs:
            rid = str(r.get("region_id") or "")
            m = re.match(r"^P(\d+)_", rid, re.IGNORECASE)
            pg = int(m.group(1)) if m else 1
            by_page.setdefault(pg, []).append(r)
        for pg in by_page:
            by_page[pg] = sort_regions(by_page[pg])

        pairs: List[Tuple[Dict[str, Any], Dict[str, Any], int, bool]] = []
        key_i = 0
        reg_i = 0
        for page_num, count in enumerate(regions_per_page, start=1):
            for r in by_page.get(page_num, [])[:count]:
                if key_i >= len(ordered):
                    break
                pairs.append((ordered[key_i], r, reg_i, True))
                key_i += 1
                reg_i += 1
        if pairs:
            return pairs

    out: List[Tuple[Dict[str, Any], Dict[str, Any], int, bool]] = []
    for i, key in enumerate(ordered):
        reg, idx, _ = find_best_region_for_key(key, regs)
        if reg:
            out.append((key, reg, idx, False))
    return out


def find_best_region_for_key(
    key: Dict[str, Any],
    regions: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], int, float]:
    """Pick the sheet region whose OCR best matches this question (embedding cosine)."""
    if not regions:
        return None, -1, -1.0
    expected = str(key.get("expected_answer") or "")
    _, model = split_key_expected_answer(expected)
    query = model or expected
    if not query.strip():
        return regions[0], 0, 0.0
    q_emb = embed_text_local(query)
    best_reg: Optional[Dict[str, Any]] = None
    best_idx = 0
    best_sim = -1.0
    for i, reg in enumerate(regions):
        text = str(reg.get("text") or "").strip()
        if not text:
            continue
        sim = cosine_similarity(q_emb, embed_text_local(text))
        if sim > best_sim:
            best_sim = sim
            best_reg = reg
            best_idx = i
    return best_reg, best_idx, best_sim


def _chunks_for_sheet_region(sheet_id: str, region_id: str) -> List[Dict[str, Any]]:
    doc = sheet_document_id(sheet_id)
    rows = list_rag_chunks_for_corpus(doc, region_id=region_id, sheet_id=sheet_id)
    if rows:
        return rows
    rid = region_id.strip().lower()
    out = []
    for c in get_rag_chunks_for_sheet(sheet_id, limit=500):
        meta = _parse_meta(c.get("meta"))
        cr = str(meta.get("region_id") or "")
        if cr == region_id or rid in cr.lower():
            out.append(c)
    return out


def build_key_bounded_corpus(
    exam_id: str,
    key: Dict[str, Any],
    *,
    student_embedding: Optional[Sequence[float]] = None,
) -> BoundedCorpus:
    qid = str(key.get("question_id") or "?")
    expected = str(key.get("expected_answer") or "")
    normalized, prompt, model, model_start, model_end = _model_char_bounds(expected)

    raw_chunks = _chunks_for_key_question(exam_id, key)
    spans: List[ChunkSpan] = []
    for row in raw_chunks:
        meta = _parse_meta(row.get("meta"))
        c0 = _int_or_none(meta.get("char_start"))
        c1 = _int_or_none(meta.get("char_end"))
        if c0 is not None and c1 is not None and normalized:
            c0 = max(model_start, c0)
            c1 = min(model_end, c1)
            if c0 >= c1:
                continue
            text = normalized[c0:c1].strip()
        else:
            text = _strip_key_wrapper(str(row.get("text_content") or ""))
        emb_sim: Optional[float] = None
        if student_embedding is not None and text:
            emb_sim = cosine_similarity(student_embedding, embed_text_local(text))
        spans.append(
            ChunkSpan(
                chunk_id=str(row.get("chunk_id") or ""),
                chunk_index=int(meta.get("answer_chunk_index", row.get("chunk_index") or 0)),
                char_start=c0,
                char_end=c1,
                text=text,
                similarity_to_student=emb_sim,
            )
        )

    assembled = assemble_from_spans(normalized, spans) if spans and normalized else model
    if not assembled:
        assembled = model

    return BoundedCorpus(
        corpus="answer_key",
        question_id=qid,
        region_id=None,
        start_marker=f"[BEGIN {qid} @model {model_start}-{model_end}]",
        end_marker=f"[END {qid} @model {model_start}-{model_end}]",
        chunk_spans=spans,
        assembled_text=assembled,
        question_prompt=prompt,
        answer_text=assembled,
    )


def build_sheet_bounded_corpus(
    sheet_id: str,
    region_id: str,
    region_ocr: str,
    *,
    student_embedding: Optional[Sequence[float]] = None,
    answer_start: Optional[int] = None,
    answer_end: Optional[int] = None,
) -> BoundedCorpus:
    raw_chunks = _chunks_for_sheet_region(sheet_id, region_id)
    spans: List[ChunkSpan] = []
    for row in raw_chunks:
        meta = _parse_meta(row.get("meta"))
        text = str(row.get("text_content") or "").strip()
        emb_sim: Optional[float] = None
        if student_embedding is not None and text:
            emb_sim = cosine_similarity(student_embedding, embed_text_local(text))
        spans.append(
            ChunkSpan(
                chunk_id=str(row.get("chunk_id") or ""),
                chunk_index=int(row.get("chunk_index") or 0),
                char_start=_int_or_none(meta.get("char_start")),
                char_end=_int_or_none(meta.get("char_end")),
                text=text,
                similarity_to_student=emb_sim,
            )
        )

    source = normalize_ocr_text((region_ocr or "").strip())
    assembled = assemble_from_spans(source, spans) if source else assemble_from_spans("", spans)
    a0 = answer_start if answer_start is not None else 0
    a1 = answer_end if answer_end is not None else len(source)
    a0 = max(0, min(a0, len(source)))
    a1 = max(a0, min(a1, len(source)))
    answer_text = source[a0:a1].strip() if source else assembled

    return BoundedCorpus(
        corpus="sheet",
        question_id="",
        region_id=region_id,
        start_marker=f"[BEGIN {region_id} @answer {a0}-{a1}]",
        end_marker=f"[END {region_id} @answer {a0}-{a1}]",
        chunk_spans=spans,
        assembled_text=answer_text or assembled,
        answer_text=answer_text or assembled,
    )


def _int_or_none(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def evaluate_bounded_pair(
    *,
    exam_id: str,
    sheet_id: str,
    key: Dict[str, Any],
    region_id: str,
    region_index: int,
    raw_ocr: str,
    formatted_student: str,
    format_method: str = "heuristic",
    sheet_answer_start: Optional[int] = None,
    sheet_answer_end: Optional[int] = None,
    region_ocr_full: Optional[str] = None,
) -> BoundedEvaluation:
    """Full key vs sheet comparison using all in-scope chunks and cosine grading."""
    full_region = normalize_ocr_text(region_ocr_full or raw_ocr)
    student_emb = embed_text_local(formatted_student or raw_ocr)
    key_corpus = build_key_bounded_corpus(exam_id, key, student_embedding=student_emb)
    sheet_corpus = build_sheet_bounded_corpus(
        sheet_id,
        region_id,
        full_region,
        student_embedding=student_emb,
        answer_start=sheet_answer_start,
        answer_end=sheet_answer_end,
    )

    model_for_sim = key_corpus.answer_text or str(key.get("expected_answer") or "")
    grade_text = (formatted_student or "").strip() or raw_ocr
    sim_raw = cosine_similarity(embed_text_local(model_for_sim), embed_text_local(grade_text))
    sim_score = apply_similarity_temperature(sim_raw)
    max_m = float(key.get("max_marks") or 0)
    awarded = round(max(0.0, min(max_m, sim_raw * max_m)), 1)

    alignments: List[Dict[str, Any]] = []
    for ks in key_corpus.chunk_spans:
        best_ss: Optional[ChunkSpan] = None
        best_sim = -1.0
        for ss in sheet_corpus.chunk_spans:
            if not ks.text or not ss.text:
                continue
            s = cosine_similarity(embed_text_local(ks.text), embed_text_local(ss.text))
            if s > best_sim:
                best_sim = s
                best_ss = ss
        alignments.append(
            {
                "key_chunk_id": ks.chunk_id,
                "key_chars": f"{ks.char_start}-{ks.char_end}",
                "sheet_chunk_id": best_ss.chunk_id if best_ss else None,
                "sheet_chars": (
                    f"{best_ss.char_start}-{best_ss.char_end}" if best_ss else None
                ),
                "chunk_similarity": round(best_sim, 4) if best_sim >= 0 else None,
                "key_to_student_sim": ks.similarity_to_student,
            }
        )

    return BoundedEvaluation(
        question_id=str(key.get("question_id") or "?"),
        region_id=region_id,
        region_index=region_index,
        max_marks=max_m,
        key=key_corpus,
        sheet_raw=sheet_corpus,
        sheet_formatted=formatted_student,
        format_method=format_method,
        similarity_raw=sim_raw,
        similarity_score=sim_score,
        awarded_marks=awarded,
        sheet_answer_start=sheet_answer_start,
        sheet_answer_end=sheet_answer_end,
        chunk_alignments=alignments,
    )


def evaluate_all_questions(
    *,
    exam_id: str,
    sheet_id: str,
    keys: List[Dict[str, Any]],
    regions: List[Dict[str, Any]],
    format_llm: bool = True,
    heuristic_only: bool = False,
    regions_per_page: Optional[List[int]] = None,
) -> List[BoundedEvaluation]:
    """
    Per-question pipeline: match region → extract answer span → LLM format → score.

    When ``regions_per_page`` matches the key count (e.g. DAA page 1 = 3 strips for Q1–Q3),
    uses positional 1:1 pairing so each OCR patch is the full student answer.
    """
    from autograder.text_format import format_student_answer

    ordered = sorted(keys, key=lambda k: int(k.get("sort_order") or 0))
    pairs = pair_keys_with_regions(keys, regions, regions_per_page=regions_per_page)
    out: List[BoundedEvaluation] = []
    for i, (key, reg, reg_idx, one_to_one) in enumerate(pairs):
        next_key = ordered[i + 1] if i + 1 < len(ordered) and not one_to_one else None
        region_id = str(reg.get("region_id") or "?")
        full_ocr = str(reg.get("text") or "")
        norm = normalize_ocr_text(full_ocr)
        if one_to_one:
            a0, a1, extracted = 0, len(norm), norm
        else:
            a0, a1, extracted = extract_sheet_answer_span(full_ocr, key, next_key)
        formatted = format_student_answer(
            extracted or full_ocr,
            key,
            force_heuristic=heuristic_only or not format_llm,
        )
        ev = evaluate_bounded_pair(
            exam_id=exam_id,
            sheet_id=sheet_id,
            key=key,
            region_id=region_id,
            region_index=reg_idx,
            raw_ocr=extracted or full_ocr,
            formatted_student=formatted.formatted,
            format_method=formatted.method,
            sheet_answer_start=a0,
            sheet_answer_end=a1,
            region_ocr_full=full_ocr,
        )
        out.append(ev)
    return out
