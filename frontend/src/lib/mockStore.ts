import type {
  AnswerKey,
  EvaluationResult,
  Exam,
  RagChunk,
  Sheet,
} from "./types";

function uid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}`;
}

function randVec(dim = 16): number[] {
  return Array.from({ length: dim }, () => +(Math.random() * 2 - 1).toFixed(3));
}

function daysAgo(d: number): string {
  return new Date(Date.now() - d * 86400_000).toISOString();
}

// ---------- seed ----------
const exams: Exam[] = [
  { id: "exam_phy_101", title: "Physics 101 — Midterm", createdAt: daysAgo(14) },
  { id: "exam_bio_204", title: "Biology 204 — Genetics Quiz", createdAt: daysAgo(8) },
  { id: "exam_math_220", title: "Calculus 220 — Final", createdAt: daysAgo(2) },
];

const keys: AnswerKey[] = [
  ...buildKeys("exam_phy_101", [
    ["Q1", "State Newton's second law.", "F = m·a; net force equals mass times acceleration.", 4],
    ["Q2", "Define momentum.", "Product of mass and velocity, p = m·v.", 3],
    ["Q3", "Explain conservation of energy.", "Energy in an isolated system is constant.", 5],
  ]),
  ...buildKeys("exam_bio_204", [
    ["Q1", "What is a Punnett square?", "A diagram predicting genotype probabilities.", 4],
    ["Q2", "Define dominant allele.", "An allele expressed in heterozygotes.", 3],
  ]),
  ...buildKeys("exam_math_220", [
    ["Q1", "Derivative of sin(x)?", "cos(x).", 2],
    ["Q2", "Integral of 1/x dx?", "ln|x| + C.", 3],
    ["Q3", "Define a limit.", "Value f(x) approaches as x → a.", 4],
    ["Q4", "Chain rule statement?", "(f∘g)' = f'(g(x))·g'(x).", 4],
  ]),
];

function buildKeys(
  examId: string,
  rows: Array<[string, string, string, number]>,
): AnswerKey[] {
  return rows.map(([qid, prompt, ans, max], i) => ({
    id: uid("key"),
    examId,
    questionId: qid,
    prompt,
    answer: ans,
    maxMarks: max,
    sortOrder: i,
    vector: randVec(),
  }));
}

const sheets: Sheet[] = [
  {
    id: "sheet_001",
    filename: "phy_midterm_alice.pdf",
    examId: "exam_phy_101",
    ocrEngine: "tesseract",
    status: "evaluated",
    createdAt: daysAgo(10),
    pageCount: 2,
    documentId: "doc_phy_alice",
  },
  {
    id: "sheet_002",
    filename: "phy_midterm_bob.pdf",
    examId: "exam_phy_101",
    ocrEngine: "easyocr",
    status: "evaluated",
    createdAt: daysAgo(9),
    pageCount: 2,
    documentId: "doc_phy_bob",
  },
  {
    id: "sheet_003",
    filename: "bio_quiz_carol.pdf",
    examId: "exam_bio_204",
    ocrEngine: "paddle",
    status: "ingested",
    createdAt: daysAgo(3),
    pageCount: 1,
    documentId: "doc_bio_carol",
  },
  {
    id: "sheet_004",
    filename: "calc_final_dan.pdf",
    examId: "exam_math_220",
    ocrEngine: "tesseract",
    status: "ingested",
    createdAt: daysAgo(1),
    pageCount: 3,
    documentId: "doc_calc_dan",
  },
];

const chunks: RagChunk[] = sheets.flatMap((s) =>
  Array.from({ length: 4 }).map((_, i) => ({
    id: uid("chunk"),
    documentId: s.documentId,
    sheetId: s.id,
    examId: s.examId ?? undefined,
    page: (i % s.pageCount) + 1,
    region: `region_${i + 1}`,
    text: sampleChunkText(s.filename, i),
    ocrConfidence: +(0.7 + Math.random() * 0.3).toFixed(2),
    vector: randVec(),
  })),
);

function sampleChunkText(name: string, i: number) {
  const variants = [
    "Newton's second law states that F = m a. The net force on an object equals mass times acceleration.",
    "Momentum p = m v. Conserved when no external force acts on the system.",
    "By conservation of energy, kinetic plus potential energy stays constant in absence of friction.",
    "A Punnett square cross AaBb × AaBb gives a 9:3:3:1 ratio.",
    "Derivative of sin(x) is cos(x); integral of 1/x dx equals ln|x| + C.",
    "The chain rule: derivative of f(g(x)) is f'(g(x)) g'(x).",
  ];
  return `[${name} • r${i + 1}] ${variants[(i + name.length) % variants.length]}`;
}

export function buildResultFromKeys(
  sheetId: string,
  examId: string,
  examKeys: AnswerKey[],
  examChunks: RagChunk[],
  confidence: number,
  partial: number,
): EvaluationResult {
  const questions = examKeys.map((k, i) => {
    const ratio = Math.max(0, Math.min(1, 0.6 + Math.random() * 0.4 - partial));
    const awarded = +(k.maxMarks * ratio).toFixed(1);
    return {
      questionId: k.questionId,
      awarded,
      max: k.maxMarks,
      ocrConfidence: +(0.6 + Math.random() * 0.4).toFixed(2),
      ocrText: `Student answer for ${k.questionId}: ${k.answer.split(" ").slice(0, 6).join(" ")}…`,
      feedback:
        ratio > 0.85
          ? "Excellent — covers the key idea clearly."
          : ratio > 0.5
            ? "Partially correct; missing one supporting detail."
            : "Misses the core concept; revisit definition.",
      rubric: {
        correctness: Math.round(ratio * 4),
        completeness: Math.round((ratio + 0.05) * 4),
        clarity: Math.round((ratio - 0.1) * 4),
        reasoning: Math.round(ratio * 4),
      },
      matchedChunkId: examChunks[i % examChunks.length]?.id,
      flags: ratio < 0.5 ? ["low_score"] : [],
    };
  });
  const total = +questions.reduce((a, q) => a + q.awarded, 0).toFixed(1);
  const max = questions.reduce((a, q) => a + q.max, 0);
  return {
    id: uid("res"),
    sheetId,
    examId,
    totalMarks: total,
    maxTotal: max,
    gradingConfidence: confidence,
    confidenceFlag: confidence > 0.85 ? "ok" : confidence > 0.7 ? "warn" : "low",
    promptHash: Math.random().toString(36).slice(2, 10),
    model: "gpt-4o-mini",
    createdAt: new Date(
      Date.now() - Math.random() * 5 * 86400_000,
    ).toISOString(),
    questions,
  };
}

export function buildResult(sheetId: string, examId: string, confidence: number, partial: number): EvaluationResult {
  const examKeys = keys.filter((k) => k.examId === examId);
  const examChunks = chunks.filter((c) => c.sheetId === sheetId);
  return buildResultFromKeys(sheetId, examId, examKeys, examChunks, confidence, partial);
}

const results: EvaluationResult[] = [
  buildResult("sheet_001", "exam_phy_101", 0.92, 0),
  buildResult("sheet_002", "exam_phy_101", 0.71, 0.4),
];

// ---------- store API ----------
export const store = {
  exams,
  keys,
  sheets,
  chunks,
  results,

  addExam(title: string): Exam {
    const e: Exam = {
      id: uid("exam"),
      title,
      createdAt: new Date().toISOString(),
    };
    exams.push(e);
    return e;
  },

  addKeys(examId: string, rows: Array<{ questionId: string; prompt: string; answer: string; maxMarks: number }>): AnswerKey[] {
    const made = rows.map((r, i) => ({
      id: uid("key"),
      examId,
      questionId: r.questionId,
      prompt: r.prompt,
      answer: r.answer,
      maxMarks: r.maxMarks,
      sortOrder: keys.filter((k) => k.examId === examId).length + i,
      vector: randVec(),
    }));
    keys.push(...made);
    return made;
  },

  addSheet(input: {
    filename: string;
    examId: string | null;
    file?: File;
    pageCount?: number;
  }): Sheet {
    const id = uid("sheet");
    const documentId = `doc_${id.slice(-8)}`;
    const fileUrl = input.file ? URL.createObjectURL(input.file) : undefined;
    const sheet: Sheet = {
      id,
      filename: input.filename,
      examId: input.examId,
      ocrEngine: "tesseract",
      status: "ingested",
      createdAt: new Date().toISOString(),
      pageCount: input.pageCount ?? 1,
      documentId,
      fileUrl,
      mimeType: input.file?.type,
    };
    sheets.push(sheet);
    // synthetic chunks
    const generated: RagChunk[] = Array.from({ length: 3 }).map((_, i) => ({
      id: uid("chunk"),
      documentId,
      sheetId: id,
      examId: input.examId ?? undefined,
      page: (i % sheet.pageCount) + 1,
      region: `region_${i + 1}`,
      text: sampleChunkText(input.filename, i),
      ocrConfidence: +(0.7 + Math.random() * 0.3).toFixed(2),
      vector: randVec(),
    }));
    chunks.push(...generated);
    return sheet;
  },

  updateSheetExam(sheetId: string, examId: string) {
    const s = sheets.find((x) => x.id === sheetId);
    if (s) {
      s.examId = examId;
      chunks
        .filter((c) => c.sheetId === sheetId)
        .forEach((c) => (c.examId = examId));
    }
  },

  addResult(r: EvaluationResult) {
    results.push(r);
    const s = sheets.find((x) => x.id === r.sheetId);
    if (s) s.status = "evaluated";
  },
};