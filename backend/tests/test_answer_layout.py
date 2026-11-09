"""Automatic answer layout (no preset): split sheet lines by marking-scheme question."""

import cv2
import numpy as np

from autograder import answer_layout
from autograder.answer_layout import detect_answer_layout, margin_label_spans, split_lines_by_key

KEYS = [
    "List the classification of disasters. Natural disasters such as earthquakes floods cyclones; man-made disasters.",
    "Differentiate hazard and disaster. A hazard is a potential threat; a disaster is the actual impact on people.",
    "Discuss the Bhopal gas tragedy: methyl isocyanate leak at the Union Carbide pesticide plant in 1984.",
]


def test_split_follows_the_text_of_each_answer():
    lines = [
        "Disasters are classified based on origin",
        "natural disasters include earthquakes floods cyclones",
        "man-made disasters result from human activity",
        "A hazard is a dangerous event or condition",
        "a disaster occurs when the impact on people is severe",
        "The Bhopal gas tragedy happened in 1984",
        "methyl isocyanate leaked from the Union Carbide plant",
    ]
    assert split_lines_by_key(lines, KEYS) == [(0, 3), (3, 5), (5, 7)]


def test_margin_label_moves_an_ambiguous_boundary():
    # the 3rd line could belong to either answer; the label on it decides
    lines = ["natural disasters earthquakes floods", "man-made disasters", "hazard disaster", "a hazard is a potential threat"]
    keys = KEYS[:2]
    assert split_lines_by_key(lines, keys, labelled=[True, False, True, False]) == [(0, 2), (2, 4)]
    assert split_lines_by_key(lines, keys, labelled=[True, False, False, True]) == [(0, 3), (3, 4)]


def test_too_few_lines_returns_none():
    assert split_lines_by_key(["only one line"], KEYS) is None


def _ruled_page(labels_at=(), h=2526, w=1785, margin_x=300):
    page = np.full((h, w), 245, np.uint8)
    for y in range(120, h - 60, 62):
        cv2.line(page, (0, y), (w, y), 40, 2)        # dark ruled lines
    cv2.line(page, (margin_x, 0), (margin_x, h), 30, 3)  # margin rule
    for y in labels_at:                               # handwritten "2nd Ans" in the margin, touching a rule
        cv2.putText(page, "2", (90, y), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 2.2, 10, 5)
        cv2.putText(page, "Ans)", (150, y - 5), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.4, 10, 4)
        cv2.line(page, (270, y - 70), (285, y + 10), 10, 4)
    return page


def test_margin_labels_found_despite_rules():
    spans = margin_label_spans(_ruled_page(labels_at=(400, 1500)))
    centres = sorted((a + b) / 2 for a, b in spans)
    assert len(centres) == 2
    assert abs(centres[0] - 375) < 80 and abs(centres[1] - 1475) < 80


def test_blank_margin_has_no_labels():
    assert margin_label_spans(_ruled_page()) == []


def test_detect_layout_spans_pages(monkeypatch):
    """An answer that continues onto the next page becomes two strips of the same question."""
    page_lines = {
        1: [(100, "Disasters are classified natural earthquakes floods"), (400, "man-made disasters human activity"),
            (900, "2Ans A hazard is a potential threat"), (1300, "a disaster is the actual impact on people")],
        2: [(150, "hazard versus disaster continued impact"), (800, "3Ans Bhopal gas tragedy 1984"),
            (1200, "methyl isocyanate leak Union Carbide plant")],
    }

    def fake_lines(gray, page):
        return [{"page": page, "y0": y, "y1": y + 50, "x0": 320, "text": t, "conf": 0.9} for y, t in page_lines[page]]

    monkeypatch.setattr(answer_layout, "_page_lines", fake_lines)
    monkeypatch.setattr(answer_layout, "margin_label_spans", lambda gray: [])
    pages = [np.full((2000, 1200), 245, np.uint8), np.full((2000, 1200), 245, np.uint8)]
    layout = detect_answer_layout(pages, KEYS)
    assert layout is not None
    assert layout.regions_per_page == [2, 2]
    q2_pages = [layout.pages[i] for i in layout.groups[1]]
    assert q2_pages == [1, 2]
    y0_q2 = layout.bboxes[layout.groups[1][0]][1]
    assert 850 <= y0_q2 <= 900  # just above "2Ans", not at an equal-split guess


def test_detect_layout_falls_back_without_ocr(monkeypatch):
    monkeypatch.setattr(answer_layout, "_page_lines", lambda gray, page: None)
    assert detect_answer_layout([np.full((100, 100), 245, np.uint8)], KEYS) is None
