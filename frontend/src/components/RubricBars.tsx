import type { RubricBreakdown } from "@/lib/api";

export function RubricBars({ rubric }: { rubric?: RubricBreakdown[] }) {
  if (!rubric || rubric.length === 0) {
    return <div className="text-xs text-muted-foreground">No rubric breakdown.</div>;
  }
  return (
    <div className="space-y-2">
      {rubric.map((r, i) => {
        const pct = r.max > 0 ? Math.min(100, (r.awarded / r.max) * 100) : 0;
        return (
          <div key={i} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{r.criterion}</span>
              <span className="font-mono text-foreground">
                {r.awarded.toFixed(1)} / {r.max}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${pct}%` }}
              />
            </div>
            {r.note && <div className="text-[11px] text-muted-foreground">{r.note}</div>}
          </div>
        );
      })}
    </div>
  );
}
