"""Exam totals with choice sections ("PART B: answer any 2 of 3")."""

from autograder.totals import apply_section_choice


def _q(qid, awarded, max_marks, section=None, pick=None):
    return {"question_id": qid, "awarded_marks": awarded, "max_marks": max_marks, "section": section, "section_pick": pick}


def test_disaster_mitigation_paper_totals_twenty():
    # PART A 3 x 2 compulsory, PART B best 2 of 3 x 7 -> printed maximum 20, not 27
    qs = [
        _q("Q1", 1.5, 2, "A", 3), _q("Q2", 2, 2, "A", 3), _q("Q3", 1, 2, "A", 3),
        _q("Q4", 5, 7, "B", 2), _q("Q5", 3, 7, "B", 2), _q("Q6", 6, 7, "B", 2),
    ]
    total, max_total, flags = apply_section_choice(qs)
    assert max_total == 20.0
    assert total == 1.5 + 2 + 1 + 5 + 6
    assert [q["counted"] for q in qs] == [True, True, True, True, False, True]
    assert flags == ["section_choice:B:best_2_of_3"]


def test_no_sections_counts_everything():
    qs = [_q("Q1", 2, 4), _q("Q2", 3, 4)]
    assert apply_section_choice(qs) == (5.0, 8.0, [])
    assert all(q["counted"] for q in qs)


def test_section_with_no_surplus_answers_counts_all():
    qs = [_q("Q4", 5, 7, "B", 2), _q("Q5", 3, 7, "B", 2)]
    total, max_total, flags = apply_section_choice(qs)
    assert (total, max_total, flags) == (8.0, 14.0, [])


def test_ties_keep_paper_order():
    qs = [_q("Q4", 4, 7, "B", 1), _q("Q5", 4, 7, "B", 1)]
    apply_section_choice(qs)
    assert [q["counted"] for q in qs] == [True, False]


def test_recomputed_after_teacher_patch():
    qs = [_q("Q4", 5, 7, "B", 2), _q("Q5", 3, 7, "B", 2), _q("Q6", 6, 7, "B", 2)]
    apply_section_choice(qs)
    qs[1]["awarded_marks"] = 7  # teacher raises Q5; now Q4 is the dropped answer
    total, _, _ = apply_section_choice(qs)
    assert total == 13.0
    assert [q["counted"] for q in qs] == [False, True, True]
