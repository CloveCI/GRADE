import { describe, it, expect } from "vitest";
import { startEvaluateStream } from "@/lib/sse";
import type { StreamEvent } from "@/lib/types";

describe("startEvaluateStream", () => {
  it("emits scripted phases ending with complete", async () => {
    const events: StreamEvent[] = [];
    await new Promise<void>((resolve, reject) => {
      const handle = startEvaluateStream({
        sheetId: "sheet_001",
        examId: "exam_phy_101",
        speed: 50, // run very fast
        onEvent: (e) => events.push(e),
        onComplete: () => resolve(),
        onError: (err) => reject(err),
      });
      setTimeout(() => {
        handle.cancel();
        reject(new Error("timeout"));
      }, 5000);
    });
    const phases = events.map((e) => e.phase);
    expect(phases[0]).toBe("started");
    expect(phases).toContain("preprocess");
    expect(phases).toContain("ocr_region");
    expect(phases).toContain("retrieve");
    expect(phases).toContain("score");
    expect(phases.at(-1)).toBe("complete");
  });
});