import type {
  AnswerKey,
  EvaluationResult,
  Exam,
  ExamSummary,
  MetricsOverview,
  RagChunk,
  RagSearchHit,
  Sheet,
} from "./types";

const RAW = import.meta.env.VITE_API_URL as string | undefined;
const API_BASE = (RAW ?? "").replace(/\/$/, "");

function toNumConfidence(v: string | number | null | undefined): number {
  if (typeof v === "number") return v;
  if (!v) return 0.75;
  const x = String(v).toLowerCase();
  if (x === "high") return 0.9;
  if (x === "medium") return 0.7;
  if (x === "low") return 0.45;
  const n = Number(x);
  return Number.isFinite(n) ? n : 0.75;
}

function toFlag(confidenceFlag: boolean | string | undefined, conf: number): "ok" | "warn" | "low" {
  if (typeof confidenceFlag === "string") {
    if (confidenceFlag === "ok" || confidenceFlag === "warn" || confidenceFlag === "low") {
      return confidenceFlag;
    }
  }
  if (confidenceFlag) return "low";
  if (conf < 0.8) return "warn";
  return "ok";
}

async function req(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = (j.detail as string) || JSON.stringify(j);
    } catch {
      // ignore
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res;
}

function mapSheet(r: Record<string, any>): Sheet {
  return {
    id: String(r.id),
    filename: String(r.filename || r.id),
    examId: (r.exam_id ?? r.examId ?? null) as string | null,
    ocrEngine: ((r.ocr_engine || "tesseract") as "tesseract" | "easyocr" | "paddle"),
    status: ((r.status || "uploaded") as "uploaded" | "ingested" | "evaluated"),
    createdAt: String(r.created_at || r.createdAt || new Date().toISOString()),
    pageCount: Number(r.page_count || r.pageCount || 1),
    documentId: String(r.document_id || r.documentId || `doc_${String(r.id).slice(0, 8)}`),
    fileUrl: `${API_BASE}/sheet/${encodeURIComponent(String(r.id))}/file`,
    mimeType: undefined,
  };
}

function mapResult(r: Record<string, any>): EvaluationResult {
  const q = Array.isArray(r.questions) ? r.questions : [];
  const conf = toNumConfidence(r.grading_confidence ?? r.gradingConfidence);
  return {
    id: String(r.id || r.result_id),
    sheetId: String(r.sheet_id || r.sheetId || ""),
    examId: String(r.exam_id || r.examId || ""),
    totalMarks: Number(r.total_marks ?? r.totalMarks ?? 0),
    maxTotal: Number(r.max_total ?? r.maxTotal ?? 0),
    gradingConfidence: conf,
    confidenceFlag: toFlag(r.confidence_flag ?? r.confidenceFlag, conf),
    promptHash: String(r.prompt_hash || r.promptHash || ""),
    model: String(r.llm_model || r.model || ""),
    createdAt: String(r.created_at || r.createdAt || new Date().toISOString()),
    questions: q.map((x: any) => ({
      questionId: String(x.question_id || x.questionId || ""),
      awarded: Number(x.awarded_marks ?? x.awarded ?? 0),
      max: Number(x.max_marks ?? x.max ?? 0),
      ocrConfidence: Number(x.ocr_confidence ?? x.ocrConfidence ?? 0),
      ocrText: String(x.student_answer ?? x.ocrText ?? ""),
      feedback: String(x.feedback ?? ""),
      rubric: {
        correctness: Number(x.rubric_scores?.factual_accuracy ?? x.rubric?.correctness ?? 0),
        completeness: Number(x.rubric_scores?.conceptual_completeness ?? x.rubric?.completeness ?? 0),
        clarity: Number(x.rubric_scores?.domain_terminology ?? x.rubric?.clarity ?? 0),
        reasoning: Number(x.rubric_scores?.reasoning ?? x.rubric?.reasoning ?? 0),
      },
      matchedChunkId: x.matched_chunk_id || x.matchedChunkId,
      flags: Array.isArray(x.flags) ? x.flags.map(String) : [],
    })),
  };
}

export const api = {
  async listExams(): Promise<Exam[]> {
    const r = await req("/api/exams");
    const rows = (await r.json()) as Array<Record<string, any>>;
    return rows.map((x) => ({
      id: String(x.id),
      title: String(x.title || x.id),
      createdAt: String(x.last_eval_at || new Date().toISOString()),
    }));
  },

  async listExamsWithCounts(): Promise<ExamSummary[]> {
    const r = await req("/api/exams");
    const rows = (await r.json()) as Array<Record<string, any>>;
    return rows.map((x) => ({
      examId: String(x.id),
      title: String(x.title || x.id),
      keyCount: Number(x.key_count || 0),
      sheetCount: Number(x.sheet_count || 0),
      lastEvalAt: x.last_eval_at ? String(x.last_eval_at) : null,
    }));
  },

  async getExam(examId: string): Promise<{ exam: Exam; keys: AnswerKey[]; sheets: Sheet[] } | null> {
    try {
      const r = await req(`/api/exams/${encodeURIComponent(examId)}`);
      const j = (await r.json()) as Record<string, any>;
      return {
        exam: {
          id: String(j.exam?.id || examId),
          title: String(j.exam?.title || examId),
          createdAt: new Date().toISOString(),
        },
        keys: (Array.isArray(j.keys) ? j.keys : []).map((k: any, i: number) => ({
          id: String(k.id),
          examId: String(k.exam_id || examId),
          questionId: String(k.question_id || ""),
          prompt: String(k.question_id || ""),
          answer: String(k.expected_answer || ""),
          maxMarks: Number(k.max_marks || 0),
          sortOrder: Number(k.sort_order ?? i),
          vector: Array.isArray(k.embedding) ? k.embedding.slice(0, 16).map(Number) : [],
        })),
        sheets: (Array.isArray(j.sheets) ? j.sheets : []).map((s: any) => mapSheet(s)),
      };
    } catch {
      return null;
    }
  },

  async createExam(title: string): Promise<Exam> {
    const id = title.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    return { id: id || "exam", title, createdAt: new Date().toISOString() };
  },

  async createKeys(
    examId: string,
    rows: Array<{ questionId: string; prompt: string; answer: string; maxMarks: number }>,
  ): Promise<AnswerKey[]> {
    const payload = {
      exam_id: examId,
      questions: rows.map((r, i) => ({
        question_id: r.questionId || `Q${i + 1}`,
        expected_answer: r.answer,
        max_marks: r.maxMarks,
        domain: "general",
      })),
    };
    const res = await req("/upload/key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const out = (await res.json()) as { key_ids: string[] };
    return out.key_ids.map((id, i) => ({
      id,
      examId,
      questionId: rows[i]?.questionId || `Q${i + 1}`,
      prompt: rows[i]?.prompt || rows[i]?.questionId || `Q${i + 1}`,
      answer: rows[i]?.answer || "",
      maxMarks: rows[i]?.maxMarks || 0,
      sortOrder: i,
      vector: [],
    }));
  },

  async listSheets(filter?: { examId?: string }): Promise<Sheet[]> {
    const q = filter?.examId ? `?exam_id=${encodeURIComponent(filter.examId)}` : "";
    const r = await req(`/api/sheets${q}`);
    const rows = (await r.json()) as Array<Record<string, any>>;
    return rows.map((x) => mapSheet(x));
  },

  async getSheet(sheetId: string): Promise<Sheet | null> {
    const rows = await this.listSheets();
    return rows.find((x) => x.id === sheetId) ?? null;
  },

  async getSheetChunks(sheetId: string): Promise<RagChunk[]> {
    const r = await req(`/api/sheet/${encodeURIComponent(sheetId)}/chunks`);
    const rows = (await r.json()) as Array<Record<string, any>>;
    return rows.map((x) => ({
      id: String(x.chunk_id),
      documentId: String(x.document_id || ""),
      sheetId,
      examId: (x.meta?.exam_id as string | undefined) ?? undefined,
      page: Number(x.page || 1),
      region: String(x.region || ""),
      text: String(x.text || ""),
      ocrConfidence: Number(x.ocr_confidence || 0),
      vector: [],
    }));
  },

  async createSheet(input: {
    filename: string;
    examId: string | null;
    file?: File;
    pageCount?: number;
  }): Promise<Sheet> {
    if (!input.file) throw new Error("Pick a file");
    const fd = new FormData();
    fd.append("file", input.file);
    if (input.examId) fd.append("exam_id", input.examId);
    const r = await req("/upload/sheet", { method: "POST", body: fd });
    const out = (await r.json()) as { sheet_id: string; filename: string };
    return mapSheet({
      id: out.sheet_id,
      filename: out.filename,
      exam_id: input.examId,
      page_count: input.pageCount || 1,
      status: "uploaded",
      ocr_engine: "unknown",
      created_at: new Date().toISOString(),
    });
  },

  async updateSheetExam(_sheetId: string, _examId: string): Promise<void> {
    throw new Error("updateSheetExam is not implemented yet");
  },

  async listResults(filter?: { examId?: string; sheetId?: string }): Promise<EvaluationResult[]> {
    const params = new URLSearchParams();
    if (filter?.examId) params.set("exam_id", filter.examId);
    if (filter?.sheetId) params.set("sheet_id", filter.sheetId);
    const q = params.toString() ? `?${params.toString()}` : "";
    const r = await req(`/api/results${q}`);
    const rows = (await r.json()) as Array<Record<string, any>>;
    return rows.map((x) => mapResult(x));
  },

  async getResult(resultId: string): Promise<EvaluationResult | null> {
    try {
      const r = await req(`/result/${encodeURIComponent(resultId)}`);
      const j = (await r.json()) as Record<string, any>;
      return mapResult({
        id: j.result_id,
        sheet_id: j.sheet_id,
        exam_id: j.exam_id,
        total_marks: j.total_marks,
        max_total: j.max_total,
        confidence_flag: j.confidence_flag,
        grading_confidence: j.grading_confidence,
        prompt_hash: j.prompt_hash,
        llm_model: j.llm_model,
        questions: j.questions,
      });
    } catch {
      return null;
    }
  },

  async metricsOverview(): Promise<MetricsOverview> {
    const r = await req("/api/metrics/overview");
    const x = (await r.json()) as Record<string, any>;
    return {
      sheets: Number(x.sheets || 0),
      keys: Number(x.keys || 0),
      results: Number(x.results || 0),
      exams: Number(x.exams || 0),
      lowConfidenceRate: Number(x.low_confidence_rate || 0),
      avgTotalPct: Number(x.avg_total_pct || 0),
      last24h: Number(x.last_24h || 0),
    };
  },

  /** Server-side checklist (LLM/Gemini is configured on the API process, not in the browser). */
  async integrations(): Promise<{
    llm_gemini?: { GRADE_ENABLE_LLM?: boolean; api_key_present?: boolean; ready?: boolean };
  }> {
    const r = await req("/api/integrations");
    return (await r.json()) as {
      llm_gemini?: { GRADE_ENABLE_LLM?: boolean; api_key_present?: boolean; ready?: boolean };
    };
  },

  /**
   * Full pipeline: load sheet PDF from storage, OCR patches, match keys, score (Gemini when
   * `GRADE_ENABLE_LLM` + `GRADE_GEMINI_API_KEY` are set on the API server), persist result.
   */
  async evaluate(input: {
    sheetId: string;
    examId: string;
    topK?: number;
    expectedNumRegions?: number | null;
    useConsensusOcr?: boolean;
  }): Promise<EvaluationResult> {
    let expectedNumRegions: number | null = input.expectedNumRegions ?? null;
    if (expectedNumRegions != null && !Number.isFinite(expectedNumRegions)) {
      expectedNumRegions = null;
    }
    const r = await req("/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sheet_id: input.sheetId,
        exam_id: input.examId,
        top_k: input.topK ?? 3,
        expected_num_regions: expectedNumRegions,
        use_consensus_ocr: input.useConsensusOcr ?? false,
      }),
    });
    const j = (await r.json()) as Record<string, any>;
    return mapResult({
      id: j.result_id,
      sheet_id: j.sheet_id,
      exam_id: j.exam_id,
      total_marks: j.total_marks,
      max_total: j.max_total,
      confidence_flag: j.confidence_flag,
      grading_confidence: j.grading_confidence,
      prompt_hash: j.prompt_hash,
      llm_model: j.llm_model,
      questions: j.questions,
      created_at: new Date().toISOString(),
    });
  },

  async ragSearch(input: {
    query: string;
    examId?: string;
    sheetId?: string;
    topK?: number;
  }): Promise<RagSearchHit[]> {
    const r = await req("/api/rag/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: input.query,
        exam_id: input.examId,
        sheet_id: input.sheetId,
        top_k: input.topK ?? 5,
      }),
    });
    const rows = (await r.json()) as Array<Record<string, any>>;
    return rows.map((x) => ({
      chunkId: String(x.chunk_id),
      documentId: String(x.document_id || ""),
      text: String(x.text || ""),
      score: Number(x.score || 0),
      page: Number(x.page || 1),
      region: String(x.region || ""),
      sheetId: x.sheet_id ? String(x.sheet_id) : undefined,
      examId: x.exam_id ? String(x.exam_id) : undefined,
    }));
  },

  saveResult(_r: EvaluationResult) {
    // no-op in real backend mode
  },

  buildSyntheticResult(_sheetId: string, _examId: string): EvaluationResult {
    throw new Error("Synthetic result is unavailable in real backend mode");
  },
};