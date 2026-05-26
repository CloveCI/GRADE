import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function ConfidenceBadge({ value }: { value?: number }) {
  if (value == null) return <Badge variant="outline">n/a</Badge>;
  const pct = Math.round(value * 100);
  const tone =
    pct >= 80 ? "border-success/40 bg-success/10 text-success" :
    pct >= 50 ? "border-warning/40 bg-warning/10 text-warning" :
                "border-destructive/40 bg-destructive/10 text-destructive";
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium", tone)}>
      {pct}% conf.
    </span>
  );
}
