"""CIE answer-sheet layout presets."""

from pathlib import Path

from autograder.exam_layouts import resolve_regions_per_page, sheet_layout_preset
from autograder.preprocessing import preprocess_sheet_for_evaluation, preprocess_options_from_env


def test_compiler_layout_preset_and_aliases():
    assert sheet_layout_preset("cie-compiler") == [3, 1, 1, 2]
    assert sheet_layout_preset("ml") == [3, 1, 1, 2]
    assert resolve_regions_per_page("ml", num_keys=7) == [3, 1, 1, 2]


def test_compiler_sheet_segments_seven_keys_four_pages():
    pdf = Path("data/uploads/sheet_phs3bnc8.pdf")
    if not pdf.is_file():
        return
    pp = preprocess_sheet_for_evaluation(
        str(pdf),
        exam_id="ml",
        num_answer_keys=7,
        regions_per_page=[3, 1, 1, 2],
        **preprocess_options_from_env(),
    )
    assert len(pp.patches) == 7
    qrs = pp.diagnostics["question_regions"]
    assert [q["page_start"] for q in qrs] == [1, 1, 1, 2, 3, 4, 4]
