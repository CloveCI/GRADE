// GRADE API client — maps FastAPI (snake_case) to companion UI types.
// VITE_API_URL empty in dev → Vite proxy to http://127.0.0.1:8000

const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...(init?.headers ?? {}),
    },
  });
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    let msg = res.statusText || `Request failed (${res.status})`;
    if (data && typeof data === "object" && "detail" in data) {
      msg = formatApiDetail((data as { detail: unknown }).detail);
    }
    throw new ApiError(res.status, msg, data);
  }
  return data as T;
}

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const loc = "loc" in item && Array.isArray(item.loc) ? item.loc.join(".") : "";
          return loc ? `${loc}: ${String(item.msg)}` : String(item.msg);
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  return JSON.stringify(detail);
}

function safeJson(t: string): unknown {
  try {
    return JSON.parse(t);
  } catch {
    return t;
  }
}

// ---------- Types (companion UI) ----------

export interface DatabaseStatus {
  configured: boolean;
  connected: boolean;
  postgres_deps_installed?: boolean;
  pgvector_extension: boolean;
  schema_ready: boolean;
  rag_ready: boolean;
  evaluation_ready: boolean;
  target?: string | null;
  error?: string | null;
  counts?: {
    answer_keys?: number;
    sheets?: number;
    rag_chunks?: number;
    evaluation_results?: number;
  };
}

export interface IntegrationsStatus {
  llm_gemini?: { ready?: boolean; GRADE_ENABLE_LLM?: boolean; api_key_present?: boolean };
  rag_storage?: { ready?: boolean; chunk_count?: number };
  evaluation_storage?: { ready?: boolean; result_count?: number };
  phase_3_db?: DatabaseStatus & { ok?: boolean };
  [k: string]: unknown;
}

export interface ExamSummary {
  exam_id: string;
  title?: string;
  key_count: number;
  sheet_count: number;
  updated_at?: string | null;
}

export interface AnswerKeyQuestion {
  question_id: string;
  question_text?: string;
  expected_answer?: string;
  max_marks?: number;
  rubric?: string;
}

export interface AnswerKey {
  exam_id: string;
  title?: string;
  questions: AnswerKeyQuestion[];
}

export interface Sheet {
  sheet_id: string;
  exam_id: string;
  filename?: string;
  pages?: number;
  ingested?: boolean;
  status?: string;
}

export interface RagChunk {
  chunk_id: string;
  text: string;
  page?: number;
  region?: string;
  score?: number;
}

export interface RubricBreakdown {
  criterion: string;
  awarded: number;
  max: number;
  note?: string;
}

export interface QuestionResult {
  question_id: string;
  region_index?: number;
  ocr_raw?: string;
  question_text?: string;
  expected_answer?: string;
  student_answer?: string;
  ocr_text?: string;
  awarded_marks: number;
  max_marks: number;
  confidence?: number;
  rationale?: string;
  rubric?: RubricBreakdown[];
  flags?: { rag_context_used?: boolean; [k: string]: unknown };
}

export interface EvaluationResult {
  result_id: string;
  sheet_id: string;
  exam_id: string;
  total_awarded: number;
  total_max: number;
  questions: QuestionResult[];
  created_at?: string;
  used_llm?: boolean;
  client_only?: boolean;
  notes?: string;
}

export interface RagSearchHit {
  corpus: string;
  chunk: RagChunk;
}

export interface MetricsOverview {
  total_exams: number;
  total_keys: number;
  total_sheets: number;
  total_results: number;
  rag_chunks: number;
  avg_score?: number;
}

export type StreamPhase =
  | "started"
  | "preprocess"
  | "ocr_region"
  | "retrieve"
  | "score"
  | "complete";

export interface StreamEvent {
  phase: StreamPhase;
  message?: string;
  progress?: number;
  detail?: unknown;
}

// ---------- Mappers ----------

function guessMime(filename: string): string | undefined {
  const n = filename.toLowerCase();
  if (n.endsWith(".pdf")) return "application/pdf";
  if (n.endsWith(".png")) return "image/png";
  if (n.endsWith(".jpg") || n.endsWith(".jpeg")) return "image/jpeg";
  return undefined;
}

function mapExamSummary(row: Record<string, unknown>): ExamSummary {
  return {
    exam_id: String(row.id ?? row.exam_id ?? ""),
    title: String(row.title ?? row.id ?? ""),
    key_count: Number(row.key_count ?? 0),
    sheet_count: Number(row.sheet_count ?? 0),
    updated_at: row.last_eval_at ? String(row.last_eval_at) : null,
  };
}

function mapSheet(row: Record<string, unknown>): Sheet {
  const id = String(row.id ?? row.sheet_id ?? "");
  const status = String(row.status ?? "uploaded");
  return {
    sheet_id: id,
    exam_id: String(row.exam_id ?? ""),
    filename: String(row.filename ?? id),
    pages: Number(row.page_count ?? row.pages ?? 1),
    ingested: status === "ingested" || status === "evaluated",
    status,
  };
}

function rubricFromScores(rs: Record<string, unknown> | undefined): RubricBreakdown[] {
  if (!rs) return [];
  const items: RubricBreakdown[] = [
    { criterion: "Factual accuracy", awarded: Number(rs.factual_accuracy ?? 0), max: 4 },
    { criterion: "Completeness", awarded: Number(rs.conceptual_completeness ?? 0), max: 4 },
    { criterion: "Terminology", awarded: Number(rs.domain_terminology ?? 0), max: 4 },
    { criterion: "Reasoning", awarded: Number(rs.reasoning ?? 0), max: 4 },
  ];
  return items.filter((x) => x.awarded > 0 || x.max > 0);
}

function confToNumber(v: unknown, ocr: number): number {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const x = v.toLowerCase();
    if (x === "high") return 0.9;
    if (x === "medium") return 0.7;
    if (x === "low") return 0.45;
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return ocr;
}

function mapQuestion(q: Record<string, unknown>, index?: number): QuestionResult {
  const flags = Array.isArray(q.flags) ? (q.flags as string[]) : [];
  const ocr = Number(q.ocr_confidence ?? 0);
  const regionIndex = Number(q.region_index ?? index ?? 0);
  const qid = String(q.question_id ?? "");
  return {
    question_id: qid,
    region_index: regionIndex,
    question_text: qid,
    expected_answer: "",
    student_answer: String(q.student_answer ?? ""),
    ocr_raw: String(q.ocr_raw ?? q.student_answer ?? ""),
    ocr_text: String(q.ocr_raw ?? q.student_answer ?? ""),
    awarded_marks: Number(q.awarded_marks ?? 0),
    max_marks: Number(q.max_marks ?? 0),
    confidence: confToNumber(q.grading_confidence, ocr),
    rationale: String(q.feedback ?? ""),
    rubric: rubricFromScores(q.rubric_scores as Record<string, unknown> | undefined),
    flags: { rag_context_used: flags.includes("rag_context_used") },
  };
}

function mapEvaluationResult(raw: Record<string, unknown>): EvaluationResult {
  const questions = Array.isArray(raw.questions)
    ? (raw.questions as Record<string, unknown>[]).map((q, i) => mapQuestion(q, i))
    : [];
  const qids = questions.map((q) => q.question_id);
  if (qids.length > 1 && new Set(qids).size < qids.length) {
    questions.forEach((q, i) => {
      q.region_index = i;
    });
  }
  const llm = String(raw.llm_model ?? "");
  return {
    result_id: String(raw.id ?? raw.result_id ?? ""),
    sheet_id: String(raw.sheet_id ?? ""),
    exam_id: String(raw.exam_id ?? ""),
    total_awarded: Number(raw.total_marks ?? raw.total_awarded ?? 0),
    total_max: Number(raw.max_total ?? raw.total_max ?? 0),
    questions,
    used_llm: llm.length > 0 && !llm.startsWith("fallback"),
    client_only: false,
  };
}

function mapRagChunkRow(row: Record<string, unknown>): RagChunk {
  const m = (row.meta ?? {}) as Record<string, unknown>;
  return {
    chunk_id: String(row.chunk_id ?? row.id ?? ""),
    text: String(row.text ?? row.text_content ?? ""),
    page: Number(row.page ?? m.source_page ?? 1),
    region: String(row.region ?? m.region_id ?? ""),
    score: row.score != null ? Number(row.score) : undefined,
  };
}

function corpusLabel(documentId: string, meta: Record<string, unknown>): string {
  if (String(meta.kind) === "answer_key" || documentId.startsWith("keys_")) return "answer_key";
  return "sheet";
}

// ---------- Connectivity ----------

export const getDatabaseStatus = () => request<DatabaseStatus>("/api/database/status");

export const getIntegrations = () => request<IntegrationsStatus>("/api/integrations");

export const getHealth = () => request<Record<string, unknown>>("/health");

// ---------- Exams & keys ----------

export const listExams = async () => {
  const rows = await request<Array<Record<string, unknown>>>("/api/exams");
  return rows.map(mapExamSummary);
};

export const getExam = async (id: string) => {
  const raw = await request<{
    exam?: Record<string, unknown>;
    keys?: Array<Record<string, unknown>>;
    sheets?: Array<Record<string, unknown>>;
  }>(`/api/exams/${encodeURIComponent(id)}`);
  const keysArr = Array.isArray(raw.keys) ? raw.keys : [];
  return {
    exam: mapExamSummary({
      id: raw.exam?.id ?? id,
      title: raw.exam?.title ?? id,
      key_count: keysArr.length,
      sheet_count: (raw.sheets ?? []).length,
    }),
    keys: {
      exam_id: id,
      title: String(raw.exam?.title ?? id),
      questions: keysArr.map((k, i) => ({
        question_id: String(k.question_id ?? `Q${i + 1}`),
        question_text: String(k.question_id ?? ""),
        expected_answer: String(k.expected_answer ?? ""),
        max_marks: Number(k.max_marks ?? 0),
      })),
    } satisfies AnswerKey,
    sheets: (raw.sheets ?? []).map(mapSheet),
  };
};

export const uploadKeyJson = (body: {
  exam_id: string;
  questions: Array<{
    question_id: string;
    expected_answer: string;
    max_marks: number;
    domain?: string;
  }>;
}) =>
  request<{ exam_id: string; key_ids?: string[] }>("/upload/key", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const uploadKeyFile = (args: {
  file: File;
  exam_id: string;
  default_max_marks?: number;
}) => {
  const fd = new FormData();
  fd.append("file", args.file);
  fd.append("exam_id", args.exam_id);
  if (args.default_max_marks != null) {
    fd.append("default_max_marks", String(args.default_max_marks));
  }
  return request<{ exam_id: string; key_ids: string[]; questions?: number }>(
    "/upload/key/file",
    { method: "POST", body: fd },
  ).then((r) => ({
    exam_id: args.exam_id,
    questions: r.key_ids?.length ?? 0,
  }));
};

export const ingestExamRag = async (examId: string, sheetId?: string) => {
  const qs = sheetId ? `?sheet_id=${encodeURIComponent(sheetId)}` : "";
  const raw = await request<Record<string, unknown>>(
    `/api/exam/${encodeURIComponent(examId)}/ingest-rag${qs}`,
    { method: "POST" },
  );
  const keys = (raw.keys ?? {}) as Record<string, unknown>;
  const sheet = (raw.sheet ?? {}) as Record<string, unknown>;
  const chunks =
    Number(keys.key_count ?? keys.chunks_saved ?? 0) +
    Number(sheet.chunks_saved ?? 0);
  return { exam_id: examId, chunks };
};

// ---------- Sheets ----------

export const listSheets = async () => {
  const rows = await request<Array<Record<string, unknown>>>("/api/sheets");
  return rows.map(mapSheet);
};

export const uploadSheet = async (args: { file: File; exam_id: string }) => {
  const fd = new FormData();
  fd.append("file", args.file);
  fd.append("exam_id", args.exam_id);
  const raw = await request<{ sheet_id: string; filename: string; exam_id?: string }>(
    "/upload/sheet",
    { method: "POST", body: fd },
  );
  return mapSheet({
    id: raw.sheet_id,
    filename: raw.filename,
    exam_id: raw.exam_id ?? args.exam_id,
    status: "ingested",
    page_count: args.file.type === "application/pdf" ? 2 : 1,
  });
};

export const uploadExamBundle = async (args: {
  exam_id: string;
  key_file: File;
  sheet_file: File;
  default_max_marks?: number;
}) => {
  const fd = new FormData();
  fd.append("exam_id", args.exam_id);
  fd.append("key_file", args.key_file);
  fd.append("sheet_file", args.sheet_file);
  if (args.default_max_marks != null) {
    fd.append("default_max_marks", String(args.default_max_marks));
  }
  const raw = await request<{
    exam_id: string;
    sheet_id: string;
    filename: string;
    key_ids: string[];
  }>("/upload/exam-bundle", { method: "POST", body: fd });
  return {
    exam_id: raw.exam_id,
    sheet_id: raw.sheet_id,
    filename: raw.filename,
  };
};

export const ingestSheet = async (sheetId: string, force = true) => {
  const raw = await request<Record<string, unknown>>(
    `/api/sheet/${encodeURIComponent(sheetId)}/ingest?force=${force}`,
    { method: "POST" },
  );
  return {
    sheet_id: sheetId,
    chunks: Number(raw.chunks_saved ?? 0),
  };
};

export const getSheetChunks = async (sheetId: string) => {
  const rows = await request<Array<Record<string, unknown>>>(
    `/api/sheet/${encodeURIComponent(sheetId)}/chunks`,
  );
  return rows.map((x) =>
    mapRagChunkRow({
      chunk_id: x.chunk_id,
      text: x.text,
      page: x.page,
      region: x.region,
      meta: x.meta,
    }),
  );
};

export const getSheetFileUrl = (sheetId: string) =>
  `${BASE}/sheet/${encodeURIComponent(sheetId)}/file`;

export const getSheetMime = (filename?: string) =>
  filename ? guessMime(filename) : undefined;

// ---------- Evaluate & results ----------

export interface EvaluateInput {
  sheet_id: string;
  exam_id: string;
  top_k?: number;
  expected_num_regions?: number | null;
  use_consensus_ocr?: boolean;
}

export const evaluate = async (input: EvaluateInput) => {
  const raw = await request<Record<string, unknown>>("/evaluate", {
    method: "POST",
    body: JSON.stringify({
      sheet_id: input.sheet_id,
      exam_id: input.exam_id,
      top_k: input.top_k ?? 3,
      expected_num_regions: input.expected_num_regions ?? null,
      use_consensus_ocr: input.use_consensus_ocr ?? false,
    }),
  });
  return mapEvaluationResult(raw);
};

export const getResult = async (id: string) => {
  const raw = await request<Record<string, unknown>>(`/result/${encodeURIComponent(id)}`);
  return mapEvaluationResult({
    ...raw,
    id: raw.result_id ?? id,
    questions: raw.questions,
  });
};

export const listResults = async () => {
  const rows = await request<Array<Record<string, unknown>>>("/api/results");
  return rows.map((r) =>
    mapEvaluationResult({
      ...r,
      id: r.id ?? r.result_id,
    }),
  );
};

export const getReportPdfUrl = (id: string) =>
  `${BASE}/report/${encodeURIComponent(id)}/pdf`;

// ---------- RAG ----------

export const ragSearch = async (args: {
  query: string;
  exam_id?: string;
  sheet_id?: string;
  top_k?: number;
}) => {
  const rows = await request<Array<Record<string, unknown>>>("/api/rag/search", {
    method: "POST",
    body: JSON.stringify({
      query: args.query,
      exam_id: args.exam_id,
      sheet_id: args.sheet_id,
      top_k: args.top_k ?? 5,
    }),
  });
  const hits: RagSearchHit[] = rows.map((row) => {
    const docId = String(row.document_id ?? "");
    const meta = (row.meta ?? {}) as Record<string, unknown>;
    return {
      corpus: corpusLabel(docId, meta),
      chunk: mapRagChunkRow({
        chunk_id: row.chunk_id,
        text: row.text,
        page: row.page,
        region: row.region,
        score: row.score,
      }),
    };
  });
  return { hits };
};

// ---------- Metrics ----------

export const getMetricsOverview = async (): Promise<MetricsOverview> => {
  const [m, db] = await Promise.all([
    request<Record<string, unknown>>("/api/metrics/overview"),
    getDatabaseStatus().catch(() => null),
  ]);
  return {
    total_exams: Number(m.exams ?? 0),
    total_keys: Number(m.keys ?? 0),
    total_sheets: Number(m.sheets ?? 0),
    total_results: Number(m.results ?? 0),
    rag_chunks: Number(db?.counts?.rag_chunks ?? 0),
    avg_score: Number(m.avg_total_pct ?? 0),
  };
};

// ---------- Helpers ----------

export const slugifyExamId = (title: string) =>
  title
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64) || `exam-${Date.now()}`;
