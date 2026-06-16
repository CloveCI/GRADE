"""Generate sheet preview images with region overlays for the UI."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2

from autograder.db import get_sheet, list_answer_keys
from autograder.exam_layouts import key_region_groups, resolve_regions_per_page
from autograder.preprocessing import (
    _extract_raw_regions,
    load_bgr_from_path,
    pdf_page_count,
    preprocess_options_from_env,
)

PREVIEW_RENDER_SCALE = 2.0

_REPO_ROOT = Path(__file__).resolve().parents[2]
PREVIEW_ROOT = _REPO_ROOT / "data" / "previews"


def preview_dir(sheet_id: str) -> Path:
    return PREVIEW_ROOT / sheet_id


def _page_region_count(
    page_idx: int,
    *,
    pages: int,
    regions_per_page: Optional[List[int]],
    num_keys: int,
) -> int:
    if regions_per_page:
        if page_idx >= len(regions_per_page):
            return 0
        return max(0, int(regions_per_page[page_idx]))
    if pages == 1:
        return num_keys if num_keys > 0 else 0
    if num_keys > 0 and pages == num_keys:
        return 1
    return 1


def _raw_to_key_index(groups: Optional[List[List[int]]]) -> Dict[int, int]:
    out: Dict[int, int] = {}
    if not groups:
        return out
    for key_i, grp in enumerate(groups):
        for raw_i in grp:
            out[raw_i] = key_i
    return out


def _render_page_image(
    sheet_path: Path,
    page_idx: int,
    bboxes: List[Tuple[int, int, int, int]],
    labels: List[str],
    out_path: Path,
) -> None:
    try:
        bgr = load_bgr_from_path(sheet_path, pdf_page_index=page_idx, pdf_render_scale=PREVIEW_RENDER_SCALE)
        color = bgr.copy()
        for bbox, label in zip(bboxes, labels):
            x, y, w, h = bbox
            cv2.rectangle(color, (x, y), (x + w, y + h), (0, 120, 255), 2)
            cv2.putText(
                color,
                label,
                (x + 4, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 120, 255),
                1,
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), color)
    except Exception as e:
        logger.warning("preview image failed sheet page=%s: %s", page_idx + 1, e)


def build_sheet_preview(sheet_id: str, *, layout: Optional[List[int]] = None) -> Dict[str, Any]:
    row = get_sheet(sheet_id)
    if not row:
        return {"status": "missing"}
    sheet_path = Path(str(row["path"]))
    if not sheet_path.is_file():
        logger.warning("preview missing file sheet=%s path=%s", sheet_id, sheet_path)
        return {"status": "missing_file"}

    exam_id = str(row.get("exam_id") or "")
    keys = list_answer_keys(exam_id) if exam_id else []
    regions_per_page = layout or resolve_regions_per_page(exam_id, num_keys=len(keys))
    groups = key_region_groups(exam_id, len(keys))
    raw_to_key = _raw_to_key_index(groups)
    opts = preprocess_options_from_env()
    pages = pdf_page_count(sheet_path)

    out_dir = preview_dir(sheet_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    regions_meta: List[Dict[str, Any]] = []
    raw_region_idx = 0

    for page_idx in range(pages):
        page_expected = _page_region_count(
            page_idx,
            pages=pages,
            regions_per_page=regions_per_page,
            num_keys=len(keys),
        )
        if page_expected < 1:
            continue
        page_raw, page_bboxes, _ = _extract_raw_regions(
            str(sheet_path),
            expected_num_regions=page_expected,
            pdf_page_index=page_idx,
            pdf_render_scale=PREVIEW_RENDER_SCALE,
            full_page=not regions_per_page,
            do_deskew=opts.get("do_deskew", True),
        )
        page_labels: List[str] = []
        for bbox in page_bboxes:
            x, y, w, h = bbox
            key_idx = raw_to_key.get(raw_region_idx, raw_region_idx)
            regions_meta.append(
                {
                    "region_index": key_idx,
                    "raw_region_index": raw_region_idx,
                    "page": page_idx + 1,
                    "bbox": [x, y, w, h],
                }
            )
            page_labels.append(f"Q{key_idx + 1}")
            raw_region_idx += 1
        _render_page_image(
            sheet_path,
            page_idx,
            page_bboxes,
            page_labels,
            out_dir / f"page{page_idx + 1}.png",
        )

    meta_path = out_dir / "regions.json"
    meta_path.write_text(
        json.dumps(
            {
                "regions": regions_meta,
                "regions_per_page": regions_per_page,
                "key_region_groups": groups,
                "page_count": pages,
                "preview_render_scale": PREVIEW_RENDER_SCALE,
            }
        ),
        encoding="utf-8",
    )
    return {"status": "ok", "sheet_id": sheet_id, "regions": len(regions_meta), "page_count": pages}


def _preview_needs_rebuild(sheet_id: str, meta_path: Path) -> bool:
    if not meta_path.is_file() or not (preview_dir(sheet_id) / "page1.png").is_file():
        return True
    row = get_sheet(sheet_id)
    exam_id = str(row.get("exam_id") or "") if row else ""
    keys = list_answer_keys(exam_id) if exam_id else []
    expected_layout = resolve_regions_per_page(exam_id, num_keys=len(keys))
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    regions = payload.get("regions") or []
    if not regions:
        return True
    if any(r.get("page") is None for r in regions):
        return True
    if payload.get("regions_per_page") != expected_layout:
        return True
    if payload.get("preview_render_scale") != PREVIEW_RENDER_SCALE:
        return True
    page_count = int(payload.get("page_count") or 1)
    for page_num in range(1, page_count + 1):
        if not preview_page_path(sheet_id, page_num).is_file():
            return True
    return False


def get_sheet_preview(sheet_id: str, *, force: bool = False) -> Dict[str, Any]:
    out_dir = preview_dir(sheet_id)
    meta_path = out_dir / "regions.json"
    if force or _preview_needs_rebuild(sheet_id, meta_path):
        build_sheet_preview(sheet_id)
    regions: List[Dict[str, Any]] = []
    page_count = 1
    regions_per_page: Optional[List[int]] = None
    if meta_path.is_file():
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            regions = payload.get("regions") or []
            page_count = int(payload.get("page_count") or 1)
            regions_per_page = payload.get("regions_per_page")
        except json.JSONDecodeError:
            regions = []
    row = get_sheet(sheet_id)
    question_regions = (row or {}).get("question_regions") or []
    return {
        "sheet_id": sheet_id,
        "page_count": page_count,
        "regions_per_page": regions_per_page,
        "page_image_url": f"/api/sheet/{sheet_id}/preview/page/1.png",
        "regions": regions,
        "question_regions": question_regions,
        "preview_render_scale": PREVIEW_RENDER_SCALE,
    }


def preview_page_path(sheet_id: str, page: int) -> Path:
    return preview_dir(sheet_id) / f"page{page}.png"
