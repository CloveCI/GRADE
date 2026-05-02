import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ChunkPreviewProps {
  text: string;
  page?: number;
  region?: string;
  score?: number;
  confidence?: number;
  highlighted?: boolean;
}

export function ChunkPreview({
  text,
  page,
  region,
  score,
  confidence,
  highlighted,
}: ChunkPreviewProps) {
  return (
    <div
      className={cn(
        "rounded-md border bg-card p-3 text-sm shadow-[var(--shadow-soft)]",
        highlighted && "border-primary ring-2 ring-primary/30",
      )}
    >
      <div className="mb-1 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
        {page !== undefined && <Badge variant="outline">p.{page}</Badge>}
        {region && <Badge variant="outline">{region}</Badge>}
        {score !== undefined && (
          <Badge variant="secondary">score {score.toFixed(2)}</Badge>
        )}
        {confidence !== undefined && (
          <Badge variant="secondary">ocr {(confidence * 100).toFixed(0)}%</Badge>
        )}
      </div>
      <p className="leading-relaxed text-foreground">{text}</p>
    </div>
  );
}