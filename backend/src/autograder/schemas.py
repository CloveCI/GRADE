from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AnswerKeyChunkOut(BaseModel):
    chunk_id: str
    chunk_index: int
    text_content: str
    embedding: List[float] = Field(default_factory=list)
    char_start: Optional[int] = None
    char_end: Optional[int] = None


class AnswerKeyItemIn(BaseModel):
    question_id: str
    expected_answer: str
    max_marks: float = Field(gt=0)
    domain: str = "general"
    rubric_override: Optional[dict] = None
    # Exam section (e.g. "B") and how many of its questions count ("answer any 2 of 3"); None = every question counts.
    section: Optional[str] = None
    section_pick: Optional[int] = Field(default=None, gt=0)


class AnswerKeyOut(BaseModel):
    id: str
    exam_id: str
    question_id: str
    expected_answer: str
    embedding: List[float] = Field(default_factory=list)
    max_marks: float
    domain: str = "general"
    rubric_override: Optional[dict] = None
    sort_order: int = 0
    section: Optional[str] = None
    section_pick: Optional[int] = None
    answer_chunks: List[AnswerKeyChunkOut] = Field(default_factory=list)


class UploadKeyRequest(BaseModel):
    exam_id: str
    questions: List[AnswerKeyItemIn]


class UploadKeyResponse(BaseModel):
    key_ids: List[str]


class UploadSheetResponse(BaseModel):
    sheet_id: str
    filename: str
    exam_id: Optional[str] = None


class UploadExamBundleResponse(BaseModel):
    exam_id: str
    key_ids: List[str]
    sheet_id: str
    filename: str
    keys_ingest: dict = Field(default_factory=dict)
    sheet_ingest: dict = Field(default_factory=dict)


class EvaluateRequest(BaseModel):
    sheet_id: str
    exam_id: str
    top_k: int = Field(default=3, ge=1, le=10)
    expected_num_regions: Optional[int] = None
    regions_per_page: Optional[List[int]] = None
    use_consensus_ocr: bool = False
    force_regrade: bool = False


class JobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress: int
    stage: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PatchQuestionRequest(BaseModel):
    awarded_marks: float = Field(ge=0)
    feedback: Optional[str] = None


class RubricScores(BaseModel):
    factual_accuracy: int = Field(ge=0, le=4)
    conceptual_completeness: int = Field(ge=0, le=4)
    reasoning: int = Field(ge=0, le=4)
    domain_terminology: int = Field(ge=0, le=4)


class EvaluationResult(BaseModel):
    awarded_marks: float = Field(ge=0)
    max_marks: float = Field(ge=0)
    rubric_scores: RubricScores
    feedback: str
    grading_confidence: str
    flags: List[str] = Field(default_factory=list)

    @field_validator("grading_confidence")
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        if v not in {"high", "medium", "low"}:
            raise ValueError("grading_confidence must be high|medium|low")
        return v


class QuestionResult(BaseModel):
    question_id: str
    question_text: str = ""  # exam question stem from marking scheme
    region_index: int = 0  # 0-based OCR patch index (unique per row when keys repeat)
    page_start: int = 1
    page_end: int = 1
    pages: List[int] = Field(default_factory=list)
    student_answer: str  # OCR after cleanup (used for grading)
    ocr_raw: str = ""  # original OCR before formatting
    awarded_marks: float
    max_marks: float
    rubric_scores: RubricScores
    feedback: str
    grading_confidence: str
    ocr_confidence: float
    flags: List[str] = Field(default_factory=list)
    section: Optional[str] = None
    section_pick: Optional[int] = None
    counted: bool = True  # False when a choice section ("best 2 of 3") drops this answer from the total


class EvaluateResponse(BaseModel):
    result_id: str
    sheet_id: str = ""
    exam_id: str = ""
    total_marks: float
    max_total: float
    confidence_flag: bool
    grading_confidence: str
    prompt_hash: str
    llm_model: str
    flags: List[str] = Field(default_factory=list)
    questions: List[QuestionResult]
    created_at: Optional[str] = None


class RubricBreakdownResponse(BaseModel):
    result_id: str
    dimension_totals: Dict[str, int]
    questions: List[QuestionResult]
