import { api } from "./api";
import { buildResult, buildResultFromKeys, store } from "./mockStore";
import type { AnswerKey, EvaluationResult, RagChunk, Sheet, StreamEvent } from "./types";

export interface StreamHandle {
  cancel: () => void;
}

export interface StreamOptions {
  sheetId: string;
  examId: string;
  onEvent: (e: StreamEvent) => void;
  onComplete: (r: EvaluationResult) => void;
  onError?: (err: Error) => void;
  speed?: number; // multiplier; 1 = default
}

/**
 * Fake SSE: scripted phases with realistic delays. Mirrors the FastAPI
 * /evaluate/stream contract: started → preprocess → ocr_region* → retrieve* → score* → complete.
 *
 * When sheet/keys are not in the in-memory mock store, loads them from the API so real IDs work.
 */
export function startEvaluateStream(opts: StreamOptions): StreamHandle {
  const speed = opts.speed ?? 1;
  let cancelled = false;
  const timers: number[] = [];

  const schedule = (ms: number, fn: () => void) => {
    const id = window.setTimeout(() => {
      if (!cancelled) fn();
    }, ms / speed);
    timers.push(id);
  };

  const emit = (phase: StreamEvent["phase"], payload: Record<string, unknown>) => {
    if (cancelled) return;
    opts.onEvent({ phase, payload, ts: Date.now() });
  };

  const clearTimers = () => {
    timers.forEach((id) => clearTimeout(id));
    timers.length = 0;
  };

  const runTimeline = (sheet: Sheet, examKeys: AnswerKey[], sheetChunks: RagChunk[]) => {
    if (cancelled) return;

    let finalResult: EvaluationResult;
    try {
      finalResult = api.buildSyntheticResult(opts.sheetId, opts.examId);
    } catch {
      finalResult = buildResultFromKeys(opts.sheetId, opts.examId, examKeys, sheetChunks, 0.82, 0.15);
    }

    let t = 0;
    schedule((t += 200), () =>
      emit("started", {
        sheetId: opts.sheetId,
        examId: opts.examId,
        expectedRegions: examKeys.length,
      }),
    );

    schedule((t += 600), () =>
      emit("preprocess", {
        regionsFound: examKeys.length,
        fallbackGrid: false,
        diagnostics: { skew: 0.4, deskewed: true },
      }),
    );

    examKeys.forEach((key, i) => {
      const q = finalResult.questions[i];
      if (!q) return;
      schedule((t += 700), () =>
        emit("ocr_region", {
          regionId: `r${i + 1}`,
          questionId: key.questionId,
          engine: sheet.ocrEngine,
          confidence: q.ocrConfidence,
          textPreview: q.ocrText,
        }),
      );
      schedule((t += 500), () =>
        emit("retrieve", {
          regionId: `r${i + 1}`,
          questionId: key.questionId,
          topK: sheetChunks.slice(0, 3).map((c, j) => ({
            chunkId: c.id,
            distance: +(0.1 + j * 0.07).toFixed(3),
            preview: (c.text?.slice(0, 80) || "") + (c.text && c.text.length > 80 ? "…" : ""),
          })),
        }),
      );
      schedule((t += 600), () =>
        emit("score", {
          questionId: key.questionId,
          awarded: q.awarded,
          max: q.max,
          rubric: q.rubric,
          gradingConfidence: +(0.7 + Math.random() * 0.3).toFixed(2),
          flags: q.flags,
        }),
      );
    });

    schedule((t += 500), () => {
      if (cancelled) return;
      api.saveResult(finalResult);
      emit("complete", {
        resultId: finalResult.id,
        totalMarks: finalResult.totalMarks,
        maxTotal: finalResult.maxTotal,
      });
      opts.onComplete(finalResult);
    });
  };

  void (async () => {
    let sheet: Sheet | undefined = store.sheets.find((s) => s.id === opts.sheetId);
    let examKeys = store.keys
      .filter((k) => k.examId === opts.examId)
      .sort((a, b) => a.sortOrder - b.sortOrder);
    let sheetChunks = store.chunks.filter((c) => c.sheetId === opts.sheetId);

    if (!sheet || examKeys.length === 0) {
      try {
        const detail = await api.getExam(opts.examId);
        if (cancelled) return;
        if (!detail || detail.keys.length === 0) {
          schedule(50, () =>
            opts.onError?.(
              new Error(
                !detail
                  ? "Could not load exam (check network or exam ID)."
                  : "No answer keys for this exam. Upload a key first.",
              ),
            ),
          );
          return;
        }
        examKeys = [...detail.keys].sort((a, b) => a.sortOrder - b.sortOrder);
        sheet =
          detail.sheets.find((s) => s.id === opts.sheetId) ?? (await api.getSheet(opts.sheetId)) ?? undefined;
        if (cancelled) return;
        if (!sheet) {
          schedule(50, () => opts.onError?.(new Error("Sheet not found for this ID.")));
          return;
        }
        sheetChunks = await api.getSheetChunks(opts.sheetId);
        if (cancelled) return;
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : String(e);
        schedule(50, () => opts.onError?.(new Error(msg)));
        return;
      }
    }

    if (cancelled) return;
    runTimeline(sheet, examKeys, sheetChunks);
  })();

  return {
    cancel: () => {
      cancelled = true;
      clearTimers();
    },
  };
}
