import { Progress } from "@/components/ui/progress";
import type { RubricBreakdown } from "@/lib/types";

const labels: Array<{ key: keyof RubricBreakdown; label: string }> = [
  { key: "correctness", label: "Correctness" },
  { key: "completeness", label: "Completeness" },
  { key: "clarity", label: "Clarity" },
  { key: "reasoning", label: "Reasoning" },
];

export function RubricBars({ rubric }: { rubric: RubricBreakdown }) {
  return (
    <div className="space-y-2">
      {labels.map(({ key, label }) => {
        const v = rubric[key];
        return (
          <div key={key} className="grid grid-cols-[100px_1fr_28px] items-center gap-3">
            <span className="text-xs text-muted-foreground">{label}</span>
            <Progress value={(v / 4) * 100} className="h-2" />
            <span className="text-xs font-medium tabular-nums text-foreground">{v}/4</span>
          </div>
        );
      })}
    </div>
  );
}