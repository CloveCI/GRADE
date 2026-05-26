import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  className?: string;
}

export function KpiCard({ label, value, hint, icon, className }: Props) {
  return (
    <Card className={cn("glass-card card-hover", className)}>
      <CardContent className="flex items-start justify-between gap-4 py-5">
        <div className="space-y-1">
          <div className="kpi-label">{label}</div>
          <div className="text-3xl font-semibold tracking-tight text-foreground">{value}</div>
          {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
        </div>
        {icon && (
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/30">
            {icon}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
