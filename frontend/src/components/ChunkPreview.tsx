import type { RagChunk } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

export function ChunkPreview({ chunk }: { chunk: RagChunk }) {
  return (
    <div className="space-y-2 rounded-lg border border-border/60 bg-card/60 p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline" className="font-mono">{chunk.chunk_id.slice(0, 8)}</Badge>
        {chunk.page != null && <span>page {chunk.page}</span>}
        {chunk.region && <span>region {chunk.region}</span>}
        {chunk.score != null && (
          <span className="ml-auto font-mono text-primary">score {chunk.score.toFixed(3)}</span>
        )}
      </div>
      <p className="line-clamp-4 whitespace-pre-wrap text-sm text-foreground/90">{chunk.text}</p>
    </div>
  );
}
