import { useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { startEvaluateStream } from "@/lib/sse";
import type { EvaluationResult, StreamEvent } from "@/lib/types";
import { Check, Loader2, AlertTriangle, Cog, ScanText, Search, Calculator, Flag } from "lucide-react";
import { cn } from "@/lib/utils";

type PhaseStatus = "pending" | "active" | "done" | "warn";

interface ProcessTimelineProps {
  sheetId: string;
  examId: string;
  autoStart?: boolean;
  onComplete?: (r: EvaluationResult) => void;
}

const phaseMeta = [
  { id: "started", label: "Started", icon: Cog },
  { id: "preprocess", label: "Preprocess", icon: Cog },
  { id: "ocr_region", label: "OCR regions", icon: ScanText },
  { id: "retrieve", label: "Retrieve chunks", icon: Search },
  { id: "score", label: "Score answers", icon: Calculator },
  { id: "complete", label: "Complete", icon: Flag },
] as const;

function StatusIcon({ status }: { status: PhaseStatus }) {
  if (status === "done") return <Check className="h-4 w-4 text-[hsl(var(--success))]" />;
  if (status === "active") return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  if (status === "warn") return <AlertTriangle className="h-4 w-4 text-[hsl(var(--warning))]" />;
  return <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />;
}

export function ProcessTimeline({ sheetId, examId, autoStart = true, onComplete }: ProcessTimelineProps) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [completed, setCompleted] = useState<EvaluationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const handleRef = useRef<{ cancel: () => void } | null>(null);

  useEffect(() => {
    if (!autoStart) return;
    setEvents([]);
    setCompleted(null);
    setError(null);
    const handle = startEvaluateStream({
      sheetId,
      examId,
      onEvent: (e) => setEvents((prev) => [...prev, e]),
      onComplete: (r) => {
        setCompleted(r);
        onComplete?.(r);
      },
      onError: (err) => setError(err.message),
    });
    handleRef.current = handle;
    return () => handle.cancel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheetId, examId, autoStart]);

  const phaseStatus = useMemo<Record<string, PhaseStatus>>(() => {
    const status: Record<string, PhaseStatus> = {
      started: "pending",
      preprocess: "pending",
      ocr_region: "pending",
      retrieve: "pending",
      score: "pending",
      complete: "pending",
    };
    const seen = new Set(events.map((e) => e.phase));
    if (seen.has("started")) status.started = "done";
    if (seen.has("preprocess")) status.preprocess = "done";
    if (seen.has("ocr_region")) status.ocr_region = completed ? "done" : "active";
    if (seen.has("retrieve")) status.retrieve = completed ? "done" : "active";
    if (seen.has("score")) status.score = completed ? "done" : "active";
    if (completed) status.complete = "done";
    else if (seen.has("score")) status.complete = "active";
    return status;
  }, [events, completed]);

  const ocrEvents = events.filter((e) => e.phase === "ocr_region");
  const retrieveEvents = events.filter((e) => e.phase === "retrieve");
  const scoreEvents = events.filter((e) => e.phase === "score");

  const totalAwarded = scoreEvents.reduce((a, e) => a + Number(e.payload.awarded ?? 0), 0);
  const totalMax = scoreEvents.reduce((a, e) => a + Number(e.payload.max ?? 0), 0);

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <Card className="h-fit">
        <CardHeader>
          <CardTitle className="text-base">Pipeline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {phaseMeta.map((p) => {
            const status = phaseStatus[p.id];
            return (
              <div
                key={p.id}
                className={cn(
                  "flex items-center gap-3 rounded-md border p-2 transition-colors",
                  status === "active" && "border-primary/40 bg-primary/5",
                  status === "done" && "bg-muted/40",
                )}
              >
                <p.icon className="h-4 w-4 text-muted-foreground" />
                <span className="flex-1 text-sm">{p.label}</span>
                <StatusIcon status={status} />
              </div>
            );
          })}
          {totalMax > 0 && (
            <div className="mt-4 space-y-1 rounded-md border bg-muted/30 p-3">
              <div className="text-xs uppercase tracking-wider text-muted-foreground">Running total</div>
              <div className="text-lg font-semibold tabular-nums">
                {totalAwarded.toFixed(1)} / {totalMax}
              </div>
              <Progress value={(totalAwarded / totalMax) * 100} className="h-2" />
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      <div className="space-y-4">
        {ocrEvents.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">OCR regions</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2">
              {ocrEvents.map((e, i) => (
                <div key={i} className="rounded-md border bg-card p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">{String(e.payload.questionId)}</Badge>
                    <Badge variant="secondary">
                      {(Number(e.payload.confidence) * 100).toFixed(0)}%
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
                    {String(e.payload.textPreview)}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {retrieveEvents.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Retrieved chunks</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {retrieveEvents.slice(-3).map((e, i) => {
                const top = (e.payload.topK as Array<{ preview: string; distance: number }>) ?? [];
                return (
                  <div key={i} className="rounded-md border bg-card p-3">
                    <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline">{String(e.payload.questionId)}</Badge>
                      <span>top {top.length}</span>
                    </div>
                    {top.map((t, j) => (
                      <div key={j} className="mt-1 text-xs">
                        <span className="text-muted-foreground tabular-nums">d={t.distance.toFixed(2)}</span>{" "}
                        <span>{t.preview}</span>
                      </div>
                    ))}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}

        {scoreEvents.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Scores</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {scoreEvents.map((e, i) => (
                <div key={i} className="flex items-center justify-between rounded-md border bg-card p-3 text-sm">
                  <Badge variant="outline">{String(e.payload.questionId)}</Badge>
                  <span className="font-medium tabular-nums">
                    {Number(e.payload.awarded).toFixed(1)} / {Number(e.payload.max)}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}