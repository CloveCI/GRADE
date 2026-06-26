"""
Image preprocessing module for GRADE.

Stages 1–3: Ingest (load, grayscale, threshold, deskew), Segment (contour-based
answer regions), Preprocess (per-patch bilateral filter, morph close, resize 384×384).

Reference: [6] G. Bradski, "The OpenCV Library," Dr. Dobb's Journal, 2000.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Defaults for OCR input normalisation (opencv proposal: 384×384)
PATCH_SIZE = 384


def preprocess_options_from_env() -> dict:
    """Patch size, PDF zoom, segmentation padding, optional full-page OCR."""
    patch_size = PATCH_SIZE
    raw_ps = os.environ.get("GRADE_OCR_PATCH_SIZE", "").strip()
    if raw_ps:
        try:
            patch_size = max(128, min(2048, int(raw_ps)))
        except ValueError:
            pass
    pdf_render_scale = 3.0
    raw_z = os.environ.get("GRADE_PDF_RENDER_SCALE", "").strip()
    if raw_z:
        try:
            pdf_render_scale = max(1.0, min(6.0, float(raw_z)))
        except ValueError:
            pass
    full_page = os.environ.get("GRADE_OCR_FULL_PAGE", "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    bbox_padding_frac = 0.04
    raw_pf = os.environ.get("GRADE_OCR_BBOX_PADDING_FRAC", "").strip()
    if raw_pf:
        try:
            bbox_padding_frac = max(0.0, min(0.2, float(raw_pf)))
        except ValueError:
            pass
    bbox_padding_px_min = 16
    raw_pm = os.environ.get("GRADE_OCR_BBOX_PADDING_PX_MIN", "").strip()
    if raw_pm:
        try:
            bbox_padding_px_min = max(0, min(120, int(raw_pm)))
        except ValueError:
            pass
    return {
        "patch_size": patch_size,
        "pdf_render_scale": pdf_render_scale,
        "full_page": full_page,
        "bbox_padding_frac": bbox_padding_frac,
        "bbox_padding_px_min": bbox_padding_px_min,
    }


def load_bgr_from_path(
    path: Union[str, Path],
    *,
    pdf_page_index: int = 0,
    pdf_render_scale: float = 3.0,
) -> np.ndarray:
    """
    Load a BGR image for preprocessing. Supports raster images via OpenCV and
    **text or scanned PDF** via PyMuPDF — ``cv2.imread`` does not read PDFs.

    For PDFs, ``pdf_page_index`` is zero-based (``0`` = first page).
    ``pdf_render_scale`` multiplies the PDF page render resolution (higher = sharper OCR).
    """
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        try:
            import fitz  # PyMuPDF
        except ImportError as e:
            raise RuntimeError(
                "Answer sheet PDFs require PyMuPDF. Install: pip install pymupdf"
            ) from e
        doc = fitz.open(path)
        try:
            if doc.page_count < 1:
                raise ValueError(f"PDF has no pages: {path}")
            if pdf_page_index < 0 or pdf_page_index >= doc.page_count:
                raise ValueError(
                    f"PDF page index {pdf_page_index} out of range (0..{doc.page_count - 1}): {path}"
                )
            page = doc.load_page(pdf_page_index)
            s = float(pdf_render_scale)
            if s <= 0:
                s = 3.0
            mat = fitz.Matrix(s, s)
            pix = page.get_pixmap(matrix=mat, alpha=False)
        finally:
            doc.close()
        h, w = pix.height, pix.width
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(h, w, pix.n)
        if pix.n == 4:
            return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {path}")
    return img

# Segment: min contour area as fraction of image area (filter tiny noise)
MIN_CONTOUR_AREA_FRAC = 0.002
MAX_CONTOUR_AREA_FRAC = 0.95
# Aspect ratio: expect roughly rectangular answer boxes (min width/height or height/width)
MIN_ASPECT_RATIO = 0.2
MAX_ASPECT_RATIO = 5.0


@dataclass
class PreprocessResult:
    """Result of full preprocessing pipeline: patches and their bounding boxes."""

    patches: List[np.ndarray]  # List of 384×384 grayscale patches (one per answer key)
    bboxes: List[Tuple[int, int, int, int]]  # (x, y, w, h) per patch, on original image
    region_ids: List[str]  # Stable ordered ids: R1, R2, ...
    used_fallback_grid: bool  # True if contour count was wrong and grid fallback was used
    diagnostics: dict  # Lightweight debug/trace metadata
    ocr_patch_groups: Optional[List[List[np.ndarray]]] = None  # per-key OCR inputs (multi-strip)


def ingest(
    image_input: Union[str, Path, np.ndarray],
    *,
    do_deskew: bool = True,
    block_size: int = 11,
    c: int = 2,
) -> np.ndarray:
    """
    Stage 1: Load image, grayscale, adaptive threshold, optional deskew.

    Args:
        image_input: File path (str/Path) or BGR image (ndarray).
        do_deskew: Whether to correct rotation via Hough line transform.
        block_size: Block size for adaptive threshold (odd).
        c: Constant subtracted from mean in adaptive threshold.

    Returns:
        Grayscale, thresholded (and optionally deskewed) image.
    """
    if isinstance(image_input, (str, Path)):
        img = load_bgr_from_path(image_input)
    else:
        img = np.asarray(image_input)
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        elif img.ndim != 3:
            raise ValueError("Image must be 2D (grayscale) or 3D (BGR/BGRA)")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if block_size % 2 == 0:
        block_size += 1
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        c,
    )

    if do_deskew:
        thresh = _deskew(thresh)

    return thresh


def _deskew(image: np.ndarray) -> np.ndarray:
    """Deskew image using Hough line transform to estimate rotation angle."""
    h, w = image.shape[:2]
    # Use edges to find dominant angle
    edges = cv2.Canny(image, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=min(w, h) // 4,
        minLineLength=min(w, h) // 4,
        maxLineGap=20,
    )
    if lines is None or len(lines) == 0:
        return image

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 != 0:
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # We want small corrections (near 0 or ±90 for horizontal/vertical lines)
            if abs(angle) < 45:
                angles.append(angle)
            elif abs(angle - 90) < 45 or abs(angle + 90) < 45:
                angles.append(angle - 90 if angle > 0 else angle + 90)
    if not angles:
        return image

    median_angle = np.median(angles)
    if abs(median_angle) < 0.5:
        return image

    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        image,
        M,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


def _expand_bbox(
    x: int,
    y: int,
    cw: int,
    ch: int,
    iw: int,
    ih: int,
    *,
    pad_frac: float,
    pad_px_min: int,
) -> Tuple[int, int, int, int]:
    """Grow bbox so strokes near edges (end of lines) are not clipped."""
    if pad_frac <= 0 and pad_px_min <= 0:
        return (x, y, cw, ch)
    pad_x = max(pad_px_min, int(cw * pad_frac))
    pad_y = max(pad_px_min, int(ch * pad_frac))
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(iw, x + cw + pad_x)
    y1 = min(ih, y + ch + pad_y)
    return (x0, y0, x1 - x0, y1 - y0)


def segment(
    image: np.ndarray,
    *,
    expected_num_regions: int | None = None,
    min_area_frac: float = MIN_CONTOUR_AREA_FRAC,
    max_area_frac: float = MAX_CONTOUR_AREA_FRAC,
    min_aspect: float = MIN_ASPECT_RATIO,
    max_aspect: float = MAX_ASPECT_RATIO,
    bbox_padding_frac: float = 0.04,
    bbox_padding_px_min: int = 16,
) -> Tuple[List[np.ndarray], List[Tuple[int, int, int, int]], bool]:
    """
    Stage 2: Extract answer regions via contours; fallback to fixed grid if count wrong.

    Returns:
        (patches, bboxes, used_fallback_grid).
        patches: list of cropped grayscale regions (variable size).
        bboxes: list of (x, y, w, h) in original image coordinates.
        used_fallback_grid: True if expected_num_regions was set and contour count
            didn't match, so a simple N-row grid was used instead.
    """
    h, w = image.shape[:2]
    total_area = h * w
    min_area = int(total_area * min_area_frac)
    max_area = int(total_area * max_area_frac)

    # Contours on thresholded image (assume image is already binary or high-contrast)
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    if np.unique(gray).size > 2:
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        # Dark (answer) regions should be foreground for findContours (white = object)
        binary = 255 - gray

    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    rects: List[Tuple[int, int, int, int]] = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw <= 0 or ch <= 0:
            continue
        aspect = min(cw, ch) / max(cw, ch)
        if aspect < min_aspect or aspect > max_aspect:
            continue
        rects.append((x, y, cw, ch))

    # Sort top-to-bottom, then left-to-right (by center y, then center x)
    def sort_key(r: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x, y, cw, ch = r
        return (y + ch // 2, x + cw // 2)

    rects.sort(key=sort_key)

    # Include a margin around each contour box — handwriting often touches bbox edges.
    padded: List[Tuple[int, int, int, int]] = []
    for (x, y, cw, ch) in rects:
        padded.append(
            _expand_bbox(
                x,
                y,
                cw,
                ch,
                w,
                h,
                pad_frac=bbox_padding_frac,
                pad_px_min=bbox_padding_px_min,
            )
        )
    rects = padded

    used_fallback = False
    if expected_num_regions is not None and len(rects) != expected_num_regions:
        logger.warning(
            "Contour count %d != expected %d; using grid fallback.",
            len(rects),
            expected_num_regions,
        )
        patches, bboxes = _segment_grid_fallback(gray, expected_num_regions)
        used_fallback = True
    else:
        patches = []
        bboxes = []
        for (x, y, cw, ch) in rects:
            patch = gray[y : y + ch, x : x + cw]
            patches.append(patch)
            bboxes.append((x, y, cw, ch))

    return patches, bboxes, used_fallback


def _row_ink_density(gray: np.ndarray) -> np.ndarray:
    """Per-row ink amount (higher = more handwriting)."""
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    _, inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    row = inv.sum(axis=1).astype(np.float64)
    k = 21
    return np.convolve(row, np.ones(k) / k, mode="same")


def _horizontal_split_bounds(
    h: int,
    num_rows: int,
    row_density: np.ndarray,
    *,
    top_frac: float = 0.06,
    bottom_frac: float = 0.06,
) -> List[int]:
    """Y boundaries for ``num_rows`` strips, snapping splits to low-ink valleys."""
    if num_rows < 1:
        return [0, h]
    y_top = int(h * top_frac)
    y_bot = int(h * (1.0 - bottom_frac))
    if y_bot <= y_top + 40:
        y_top, y_bot = 0, h
    if num_rows == 1:
        return [y_top, y_bot]

    bounds = [y_top]
    content_h = y_bot - y_top

    if num_rows == 2:
        # Two answers per page — pick the whitespace valley closest to mid-page (not the
        # deepest valley, which may be *within* a multi-part answer on the lower strip).
        ideal = y_top + content_h // 2
        search_lo = int(y_top + content_h * 0.28)
        search_hi = int(y_top + content_h * 0.72)
        candidates: List[Tuple[int, float, int]] = []
        for i in range(search_lo + 8, search_hi - 8):
            if row_density[i] <= row_density[i - 1] and row_density[i] <= row_density[i + 1]:
                candidates.append((i, float(row_density[i]), abs(i - ideal)))
        split = ideal
        if candidates:
            candidates.sort(key=lambda c: (c[2], c[1]))
            split = candidates[0][0]
        bounds.extend([split, y_bot])
        for i in range(1, len(bounds)):
            bounds[i] = max(bounds[i], bounds[i - 1] + 8)
        bounds[-1] = min(h, bounds[-1])
        return bounds

    window = max(24, int(content_h * 0.10))
    for i in range(1, num_rows):
        ideal = y_top + int(content_h * i / num_rows)
        lo = max(y_top + 16, ideal - window)
        hi = min(y_bot - 16, ideal + window)
        if hi <= lo:
            bounds.append(ideal)
            continue
        band = row_density[lo:hi]
        best = lo + int(np.argmin(band))
        bounds.append(best)
    bounds.append(y_bot)
    # enforce monotonic splits
    for i in range(1, len(bounds)):
        bounds[i] = max(bounds[i], bounds[i - 1] + 8)
    bounds[-1] = min(h, bounds[-1])
    return bounds


def _segment_grid_fallback(
    image: np.ndarray, num_rows: int
) -> Tuple[List[np.ndarray], List[Tuple[int, int, int, int]]]:
    """Split image into horizontal strips; boundaries follow whitespace valleys when possible."""
    h, w = image.shape[:2]
    density = _row_ink_density(image)
    bounds = _horizontal_split_bounds(h, num_rows, density)
    patches: List[np.ndarray] = []
    bboxes: List[Tuple[int, int, int, int]] = []
    for i in range(num_rows):
        y1 = bounds[i]
        y2 = bounds[i + 1] if i + 1 < len(bounds) else h
        if y2 <= y1:
            continue
        patch = image[y1:y2, :]
        patches.append(patch)
        bboxes.append((0, y1, w, y2 - y1))
    return patches, bboxes


def _stitch_patches_vertical(patches: List[np.ndarray]) -> np.ndarray:
    """Stack grayscale patches top-to-bottom for multi-page / multi-strip answers."""
    if not patches:
        return np.zeros((1, 1), dtype=np.uint8)
    if len(patches) == 1:
        p = patches[0]
        return p if p.ndim == 2 else cv2.cvtColor(p, cv2.COLOR_BGR2GRAY)
    normed: List[np.ndarray] = []
    max_w = 0
    for p in patches:
        g = p if p.ndim == 2 else cv2.cvtColor(p, cv2.COLOR_BGR2GRAY)
        normed.append(g)
        max_w = max(max_w, g.shape[1])
    total_h = sum(g.shape[0] for g in normed)
    canvas = np.full((total_h, max_w), 255, dtype=np.uint8)
    y = 0
    for g in normed:
        canvas[y : y + g.shape[0], : g.shape[1]] = g
        y += g.shape[0]
    return canvas


def _merge_bboxes(bboxes: List[Tuple[int, int, int, int]]) -> Tuple[int, int, int, int]:
    if not bboxes:
        return (0, 0, 0, 0)
    x0 = min(b[0] for b in bboxes)
    y0 = min(b[1] for b in bboxes)
    x1 = max(b[0] + b[2] for b in bboxes)
    y1 = max(b[1] + b[3] for b in bboxes)
    return (x0, y0, x1 - x0, y1 - y0)


def preprocess_patch(
    patch: np.ndarray,
    *,
    size: int = PATCH_SIZE,
    bilateral_d: int = 5,
    bilateral_sigma: float = 75.0,
    morph_kernel_size: Tuple[int, int] = (3, 3),
) -> np.ndarray:
    """
    Stage 3 (per-patch): Bilateral filter, morphological closing, resize to size×size.

    Args:
        patch: Grayscale patch (any size).
        size: Output width and height (default 384).
        bilateral_d, bilateral_sigma: Bilateral filter params.
        morph_kernel_size: Kernel for morphological closing.

    Returns:
        Grayscale image of shape (size, size).
    """
    if patch.ndim == 3:
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    filtered = cv2.bilateralFilter(patch, bilateral_d, bilateral_sigma, bilateral_sigma)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, morph_kernel_size)
    closed = cv2.morphologyEx(filtered, cv2.MORPH_CLOSE, kernel)
    resized = cv2.resize(closed, (size, size), interpolation=cv2.INTER_LINEAR)
    return resized


def _extract_raw_regions(
    image_input: Union[str, Path, np.ndarray],
    *,
    expected_num_regions: int | None = None,
    do_deskew: bool = True,
    pdf_page_index: int = 0,
    pdf_render_scale: float = 3.0,
    full_page: bool = False,
    bbox_padding_frac: float = 0.04,
    bbox_padding_px_min: int = 16,
) -> Tuple[List[np.ndarray], List[Tuple[int, int, int, int]], bool]:
    """Load one page/sheet and return raw grayscale region crops (before 384 resize)."""
    if isinstance(image_input, (str, Path)):
        p = Path(image_input)
        orig = (
            load_bgr_from_path(
                image_input,
                pdf_page_index=pdf_page_index,
                pdf_render_scale=pdf_render_scale,
            )
            if p.suffix.lower() == ".pdf"
            else load_bgr_from_path(image_input)
        )
        ingest(orig, do_deskew=do_deskew)
    else:
        orig = (
            cv2.cvtColor(image_input, cv2.COLOR_GRAY2BGR)
            if image_input.ndim == 2
            else image_input
        )
    orig_gray = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
    if do_deskew:
        orig_gray = _deskew(orig_gray)
    if full_page:
        gh, gw = orig_gray.shape[:2]
        return [orig_gray], [(0, 0, gw, gh)], False
    if expected_num_regions is not None and expected_num_regions >= 1:
        patches_raw, bboxes = _segment_grid_fallback(orig_gray, expected_num_regions)
        return patches_raw, bboxes, True
    patches_raw, bboxes, used_fallback = segment(
        orig_gray,
        expected_num_regions=expected_num_regions,
        bbox_padding_frac=bbox_padding_frac,
        bbox_padding_px_min=bbox_padding_px_min,
    )
    return patches_raw, bboxes, used_fallback


def preprocess_pipeline(
    image_input: Union[str, Path, np.ndarray],
    *,
    expected_num_regions: int | None = None,
    patch_size: int = PATCH_SIZE,
    do_deskew: bool = True,
    pdf_page_index: int = 0,
    pdf_render_scale: float = 3.0,
    full_page: bool = False,
    bbox_padding_frac: float = 0.04,
    bbox_padding_px_min: int = 16,
) -> PreprocessResult:
    """
    Run full preprocessing: ingest → segment → preprocess_patch for each region.

    Args:
        image_input: Path to scanned answer sheet (JPEG/PNG/**PDF**; page set by ``pdf_page_index``) or image array.
        expected_num_regions: If set, contour count is validated; on mismatch, grid fallback is used.
        patch_size: Output patch side length (default 384).
        do_deskew: Whether to deskew in ingest stage.
        pdf_page_index: For ``.pdf`` paths only: zero-based page index (ignored for arrays / raster paths).
        pdf_render_scale: For ``.pdf`` paths only: PyMuPDF zoom factor (ignored for rasters).
        full_page: If True, skip contour segmentation and OCR the whole deskewed page once
            (best when regions would cut through sentences or redactions confuse layout).
        bbox_padding_frac / bbox_padding_px_min: Expand each contour bbox before crop (ignored if full_page).

    Returns:
        PreprocessResult with list of size×size patches, bboxes, and fallback flag.
    """
    patches_raw, bboxes, used_fallback = _extract_raw_regions(
        image_input,
        expected_num_regions=expected_num_regions,
        do_deskew=do_deskew,
        pdf_page_index=pdf_page_index,
        pdf_render_scale=pdf_render_scale,
        full_page=full_page,
        bbox_padding_frac=bbox_padding_frac,
        bbox_padding_px_min=bbox_padding_px_min,
    )
    patches_384 = [preprocess_patch(p, size=patch_size) for p in patches_raw]
    region_ids = [f"R{i+1}" for i in range(len(patches_384))]
    return PreprocessResult(
        patches=patches_384,
        bboxes=bboxes,
        region_ids=region_ids,
        used_fallback_grid=used_fallback,
        diagnostics={
            "num_regions": len(patches_384),
            "expected_num_regions": expected_num_regions,
            "patch_size": patch_size,
            "pdf_page_index": pdf_page_index
            if isinstance(image_input, (str, Path))
            and Path(image_input).suffix.lower() == ".pdf"
            else None,
            "pdf_render_scale": pdf_render_scale
            if isinstance(image_input, (str, Path))
            and Path(image_input).suffix.lower() == ".pdf"
            else None,
            "full_page": full_page,
        },
    )


def _apply_key_region_groups(
    raw_patches: List[np.ndarray],
    bboxes: List[Tuple[int, int, int, int]],
    region_ids: List[str],
    groups: List[List[int]],
    *,
    patch_size: int = PATCH_SIZE,
) -> Tuple[
    List[np.ndarray],
    List[Tuple[int, int, int, int]],
    List[str],
    List[List[np.ndarray]],
]:
    """Merge raw strips per answer key; keep high-res OCR strips per key."""
    out_patches: List[np.ndarray] = []
    out_bboxes: List[Tuple[int, int, int, int]] = []
    out_ids: List[str] = []
    ocr_groups: List[List[np.ndarray]] = []
    for gi, grp in enumerate(groups):
        parts = [raw_patches[i] for i in grp if i < len(raw_patches)]
        if not parts:
            continue
        # Keep OCR groups in original high-resolution grayscale to avoid square-resize
        # distortion on handwriting (especially long text lines).
        ocr_groups.append(parts)
        out_patches.append(preprocess_patch(parts[0], size=patch_size))
        out_bboxes.append(_merge_bboxes([bboxes[i] for i in grp if i < len(bboxes)]))
        ids = [region_ids[i] for i in grp if i < len(region_ids)]
        out_ids.append(ids[0] if len(ids) == 1 else "+".join(ids))
    return out_patches, out_bboxes, out_ids, ocr_groups


def pdf_page_count(image_input: Union[str, Path]) -> int:
    """Number of pages in a PDF, or 1 for raster images."""
    path = Path(image_input)
    if path.suffix.lower() != ".pdf":
        return 1
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError("PDF sheets require pymupdf (pip install pymupdf)") from e
    doc = fitz.open(str(path))
    try:
        return max(1, len(doc))
    finally:
        doc.close()


def preprocess_sheet_for_evaluation(
    image_input: Union[str, Path],
    *,
    exam_id: str = "",
    num_answer_keys: int = 0,
    expected_num_regions: int | None = None,
    regions_per_page: List[int] | None = None,
    **pipeline_kwargs: Any,
) -> PreprocessResult:
    """
    Collect OCR patches for an answer sheet (all PDF pages).

    When ``regions_per_page`` is set (e.g. ``[2, 2, 1, 1, 1]`` for CIE DM sheets), each PDF page
    gets that many horizontal strips. Optional per-exam key groups merge raw strips (e.g. Q4 on two pages).
    """
    from autograder.exam_layouts import key_region_groups

    path = Path(image_input)
    pages = pdf_page_count(path)
    patch_size = int(pipeline_kwargs.get("patch_size") or PATCH_SIZE)
    groups = key_region_groups(exam_id, num_answer_keys)

    if pages == 1 and not groups:
        exp = expected_num_regions
        if exp is None and num_answer_keys > 0:
            exp = num_answer_keys
        return preprocess_pipeline(
            image_input,
            expected_num_regions=exp,
            **pipeline_kwargs,
        )

    one_per_page = num_answer_keys > 0 and pages == num_answer_keys
    default_full_page_per_pdf_page = (
        pages > 1 and expected_num_regions is None and not regions_per_page
    )
    raw_patches: List[np.ndarray] = []
    all_bboxes: List[Tuple[int, int, int, int]] = []
    all_region_ids: List[str] = []
    raw_segments: List[dict] = []
    used_fallback = False
    page_meta: List[dict] = []

    for page_idx in range(pages):
        kw = dict(pipeline_kwargs)
        if regions_per_page:
            if page_idx >= len(regions_per_page):
                page_meta.append({"page": page_idx + 1, "regions": 0, "skipped": True})
                continue
            page_expected = int(regions_per_page[page_idx])
            if page_expected < 1:
                page_meta.append({"page": page_idx + 1, "regions": 0, "skipped": True})
                continue
            kw["full_page"] = False
        elif one_per_page or default_full_page_per_pdf_page:
            kw["full_page"] = True
            page_expected = 1
        else:
            kw["full_page"] = True
            page_expected = 1
        page_raw, page_bboxes, page_fallback = _extract_raw_regions(
            image_input,
            expected_num_regions=page_expected,
            pdf_page_index=page_idx,
            do_deskew=kw.get("do_deskew", True),
            pdf_render_scale=float(kw.get("pdf_render_scale") or 3.0),
            full_page=bool(kw.get("full_page")),
            bbox_padding_frac=float(kw.get("bbox_padding_frac") or 0.04),
            bbox_padding_px_min=int(kw.get("bbox_padding_px_min") or 16),
        )
        used_fallback = used_fallback or page_fallback
        page_meta.append({"page": page_idx + 1, "regions": len(page_raw)})
        for i, _ in enumerate(page_raw):
            prefix = f"P{page_idx + 1}_"
            rid = f"{prefix}R{i + 1}"
            all_region_ids.append(rid)
            raw_patches.append(page_raw[i])
            all_bboxes.append(page_bboxes[i])
            x, y, w, h = page_bboxes[i]
            raw_segments.append(
                {
                    "raw_region_index": len(raw_segments),
                    "region_id": rid,
                    "page": page_idx + 1,
                    "bbox": [x, y, w, h],
                    "x_start": x,
                    "x_end": x + w,
                    "y_start": y,
                    "y_end": y + h,
                }
            )

    if groups and raw_patches:
        all_patches, all_bboxes, all_region_ids, ocr_groups = _apply_key_region_groups(
            raw_patches,
            all_bboxes,
            all_region_ids,
            groups,
            patch_size=patch_size,
        )
    else:
        all_patches = [preprocess_patch(p, size=patch_size) for p in raw_patches]
        # OCR on raw strips yields better fidelity than resized 384x384 patches.
        ocr_groups = [[p] for p in raw_patches]

    question_regions: List[dict] = []
    if groups:
        for q_idx, grp in enumerate(groups):
            segs = [raw_segments[i] for i in grp if i < len(raw_segments)]
            if not segs:
                continue
            pages_for_q = sorted({int(s["page"]) for s in segs})
            question_regions.append(
                {
                    "question_index": q_idx,
                    "region_index": q_idx,
                    "raw_region_indices": [int(s["raw_region_index"]) for s in segs],
                    "region_ids": [str(s["region_id"]) for s in segs],
                    "page_start": pages_for_q[0],
                    "page_end": pages_for_q[-1],
                    "pages": pages_for_q,
                    "segments": segs,
                }
            )
    else:
        for q_idx, seg in enumerate(raw_segments[: len(all_patches)]):
            question_regions.append(
                {
                    "question_index": q_idx,
                    "region_index": q_idx,
                    "raw_region_indices": [int(seg["raw_region_index"])],
                    "region_ids": [str(seg["region_id"])],
                    "page_start": int(seg["page"]),
                    "page_end": int(seg["page"]),
                    "pages": [int(seg["page"])],
                    "segments": [seg],
                }
            )

    return PreprocessResult(
        patches=all_patches,
        bboxes=all_bboxes,
        region_ids=all_region_ids,
        used_fallback_grid=used_fallback,
        ocr_patch_groups=ocr_groups,
        diagnostics={
            "num_regions": len(all_patches),
            "pdf_pages": pages,
            "one_region_per_page": one_per_page or default_full_page_per_pdf_page,
            "num_answer_keys": num_answer_keys,
            "expected_num_regions": expected_num_regions,
            "regions_per_page": regions_per_page,
            "key_region_groups": groups,
            "question_regions": question_regions,
            "pages": page_meta,
        },
    )
