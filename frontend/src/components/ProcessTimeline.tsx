import type { StreamEvent, StreamPhase } from "@/lib/api";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  events: StreamEvent[];
  active?: boolean;
  demo?: boolean;
}

const PHASE_ORDER: { phase: StreamPhase; label: string }[] = [
  { phase: "started", label: "Started" },
  { phase: "preprocess", label: "Preprocess" },
  { phase: "ocr_region", label: "OCR regions" },
  { phase: "retrieve", label: "Hybrid RAG retrieve" },
  { phase: "score", label: "Score with rubric" },
  { phase: "complete", label: "Complete" },
];

export function ProcessTimeline({ events, active, demo }: Props) {
  const seen = new Set(events.map((e) => e.phase));
  const lastIdx = events.length - 1;
  return (
    <div className="space-y-3">
      {demo && (
        <div className="rounded-md border border-warning/40 bg-warning/5 px-3 py-1.5 text-[11px] uppercase tracking-wider text-warning">
          Demo timeline · synthetic
        </div>
      )}
      <ol className="relative space-y-3 border-l border-border/60 pl-5">
        {PHASE_ORDER.map((p, idx) => {
          const done = seen.has(p.phase);
          const isCurrent = active && events[lastIdx]?.phase === p.phase;
          const Icon = done ? CheckCircle2 : isCurrent ? Loader2 : Circle;
          return (
            <li key={p.phase} className="relative">
              <span
                className={cn(
                  "absolute -left-[27px] top-0 flex h-5 w-5 items-center justify-center rounded-full border bg-background",
                  done
                    ? "border-success/60 text-success"
                    : isCurrent
                      ? "border-primary/60 text-primary"
                      : "border-border text-muted-foreground",
                )}
              >
                <Icon className={cn("h-3.5 w-3.5", isCurrent && "animate-spin")} />
              </span>
              <div className="text-sm font-medium text-foreground">{p.label}</div>
              <div className="text-xs text-muted-foreground">
                {events.find((e) => e.phase === p.phase)?.message ?? (done ? "done" : "pending")}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
