import { Card, CardContent } from "@/components/ui/card";
import type { LucideIcon } from "lucide-react";

interface KpiCardProps {
  label: string;
  value: string | number;
  hint?: string;
  icon?: LucideIcon;
  tone?: "default" | "success" | "warning" | "danger";
}

const toneClass: Record<NonNullable<KpiCardProps["tone"]>, string> = {
  default: "bg-primary/10 text-primary",
  success: "bg-[hsl(var(--success))]/15 text-[hsl(var(--success))]",
  warning: "bg-[hsl(var(--warning))]/15 text-[hsl(var(--warning))]",
  danger: "bg-destructive/15 text-destructive",
};

export function KpiCard({ label, value, hint, icon: Icon, tone = "default" }: KpiCardProps) {
  return (
    <Card className="shadow-[var(--shadow-soft)]">
      <CardContent className="flex items-center gap-4 p-5">
        {Icon && (
          <div className={`flex h-11 w-11 items-center justify-center rounded-md ${toneClass[tone]}`}>
            <Icon className="h-5 w-5" />
          </div>
        )}
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
          <div className="mt-0.5 text-2xl font-semibold tracking-tight text-foreground">{value}</div>
          {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
        </div>
      </CardContent>
    </Card>
  );
}