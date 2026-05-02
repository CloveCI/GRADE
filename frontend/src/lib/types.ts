export interface Exam {
  id: string;
  title: string;
  createdAt: string;
}

export interface AnswerKey {
  id: string;
  examId: string;
  questionId: string;
  prompt: string;
  answer: string;
  maxMarks: number;
  sortOrder: number;
  vector: number[]; // 16-D preview
}

export type SheetStatus = "uploaded" | "ingested" | "evaluated";

export interface Sheet {
  id: string;
  filename: string;
  examId: string | null;
  ocrEngine: "tesseract" | "easyocr" | "paddle";
  status: SheetStatus;
  createdAt: string;
  pageCount: number;
  documentId: string;
  fileUrl?: string;
  mimeType?: string;
}

export interface RagChunk {
  id: string;
  documentId: string;
  sheetId?: string;
  examId?: string;
  page: number;
  region: string;
  text: string;
  ocrConfidence: number;
  vector: number[]; // 16-D preview
}

export interface RubricBreakdown {
  correctness: number; // 0..4
  completeness: number;
  clarity: number;
  reasoning: number;
}

export interface QuestionResult {
  questionId: string;
  awarded: number;
  max: number;
  ocrConfidence: number;
  ocrText: string;
  feedback: string;
  rubric: RubricBreakdown;
  matchedChunkId?: string;
  flags: string[];
}

export interface EvaluationResult {
  id: string;
  sheetId: string;
  examId: string;
  totalMarks: number;
  maxTotal: number;
  gradingConfidence: number; // 0..1
  confidenceFlag: "ok" | "low" | "warn";
  promptHash: string;
  model: string;
  createdAt: string;
  questions: QuestionResult[];
}

export interface MetricsOverview {
  sheets: number;
  keys: number;
  results: number;
  exams: number;
  lowConfidenceRate: number;
  avgTotalPct: number;
  last24h: number;
}

export interface ExamSummary {
  examId: string;
  title: string;
  keyCount: number;
  sheetCount: number;
  lastEvalAt: string | null;
}

export interface RagSearchHit {
  chunkId: string;
  documentId: string;
  text: string;
  score: number;
  page: number;
  region: string;
  sheetId?: string;
  examId?: string;
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
  payload: Record<string, unknown>;
  ts: number;
}