import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface PagePlaceholderProps {
  title: string;
  description: string;
  phase: string;
  bullets?: string[];
}

export function PagePlaceholder({ title, description, phase, bullets }: PagePlaceholderProps) {
  return (
    <div className="mx-auto max-w-3xl">
      <Card className="border-dashed shadow-[var(--shadow-soft)]">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-2xl">{title}</CardTitle>
            <Badge variant="secondary" className="uppercase tracking-wider">
              {phase}
            </Badge>
          </div>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        {bullets && bullets.length > 0 && (
          <CardContent>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {bullets.map((b) => (
                <li key={b} className="flex gap-2">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        )}
      </Card>
    </div>
  );
}