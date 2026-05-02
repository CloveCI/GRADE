import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function ConfidenceBadge({ value, flag }: { value: number; flag?: "ok" | "low" | "warn" }) {
  const inferred = flag ?? (value > 0.85 ? "ok" : value > 0.7 ? "warn" : "low");
  const cls =
    inferred === "ok"
      ? "bg-[hsl(var(--success))]/15 text-[hsl(var(--success))] border-[hsl(var(--success))]/30"
      : inferred === "warn"
        ? "bg-[hsl(var(--warning))]/15 text-[hsl(var(--warning))] border-[hsl(var(--warning))]/30"
        : "bg-destructive/15 text-destructive border-destructive/30";
  return (
    <Badge variant="outline" className={cn("font-medium", cls)}>
      {(value * 100).toFixed(0)}%
    </Badge>
  );
}