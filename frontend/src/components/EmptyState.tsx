import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

interface Props {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: Props) {
  return (
    <Card className="glass-card">
      <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
        {icon && <div className="text-primary/80">{icon}</div>}
        <div className="text-base font-medium text-foreground">{title}</div>
        {description && (
          <p className="max-w-md text-sm text-muted-foreground">{description}</p>
        )}
        {action}
      </CardContent>
    </Card>
  );
}
