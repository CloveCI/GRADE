"""Exam totals, including choice sections ("PART B: answer any 2 of 3 questions").

A question counts unless its section has ``section_pick`` set and more answered questions than that, in which case
only the best ``section_pick`` answers count. ``max_total`` counts the section's ``section_pick`` largest maxima,
so a 3 x 7-mark section with "any 2" contributes 14, matching the printed paper total.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Tuple


def apply_section_choice(questions: List[Dict[str, Any]]) -> Tuple[float, float, List[str]]:
    """Set ``counted`` on each question dict (in place) and return ``(total_marks, max_total, flags)``."""
    groups: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    total = 0.0
    max_total = 0.0
    flags: List[str] = []
    for q in questions:
        sec = str(q.get("section") or "").strip()
        pick = int(q.get("section_pick") or 0)
        if sec and pick > 0:
            groups.setdefault(sec, []).append(q)
            continue
        q["counted"] = True
        total += float(q.get("awarded_marks") or 0)
        max_total += float(q.get("max_marks") or 0)

    for sec, qs in groups.items():
        pick = int(qs[0].get("section_pick") or 0)
        if len(qs) <= pick:
            chosen = qs
        else:
            # best answers first; ties keep paper order (sorted() is stable)
            chosen = sorted(qs, key=lambda q: -float(q.get("awarded_marks") or 0))[:pick]
            flags.append(f"section_choice:{sec}:best_{pick}_of_{len(qs)}")
        chosen_ids = {id(q) for q in chosen}
        for q in qs:
            q["counted"] = id(q) in chosen_ids
        total += sum(float(q.get("awarded_marks") or 0) for q in chosen)
        maxima = sorted((float(q.get("max_marks") or 0) for q in qs), reverse=True)
        max_total += sum(maxima[:pick])
    return round(total, 1), round(max_total, 1), flags
