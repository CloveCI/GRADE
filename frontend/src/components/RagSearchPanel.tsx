import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { ragSearch, type RagSearchHit } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChunkPreview } from "./ChunkPreview";

interface Props {
  examId?: string;
  sheetId?: string;
  defaultQuery?: string;
}

export function RagSearchPanel({ examId, sheetId, defaultQuery = "" }: Props) {
  const [query, setQuery] = useState(defaultQuery);
  const [topK, setTopK] = useState(5);
  const m = useMutation({
    mutationFn: () => ragSearch({ query, exam_id: examId, sheet_id: sheetId, top_k: topK }),
  });

  const hits: RagSearchHit[] = m.data?.hits ?? [];

  return (
    <Card className="glass-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Search className="h-4 w-4 text-primary" /> RAG search
        </CardTitle>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {examId && <Badge variant="outline">exam: {examId}</Badge>}
          {sheetId && <Badge variant="outline">sheet: {sheetId.slice(0, 8)}</Badge>}
          {examId && sheetId && <span>searching both corpora</span>}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (query.trim()) m.mutate();
          }}
        >
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. mitochondria role in respiration"
          />
          <Input
            type="number"
            min={1}
            max={25}
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value) || 5)}
            className="sm:w-24"
          />
          <Button type="submit" disabled={m.isPending || !query.trim()}>
            {m.isPending ? "Searching…" : "Search"}
          </Button>
        </form>
        {m.isError && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
            {(m.error as Error).message}
          </div>
        )}
        <div className="space-y-2">
          {hits.length === 0 && m.isSuccess && (
            <div className="text-xs text-muted-foreground">No hits for that query.</div>
          )}
          {hits.map((h, i) => (
            <div key={i} className="space-y-1">
              <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
                {h.corpus}
              </Badge>
              <ChunkPreview chunk={h.chunk} />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
