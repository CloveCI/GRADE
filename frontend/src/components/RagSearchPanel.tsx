import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Loader2, Search } from "lucide-react";
import { ChunkPreview } from "./ChunkPreview";

interface RagSearchPanelProps {
  examId?: string;
  sheetId?: string;
  compact?: boolean;
}

export function RagSearchPanel({ examId, sheetId, compact }: RagSearchPanelProps) {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");

  const { data, isFetching } = useQuery({
    queryKey: ["rag", submitted, examId, sheetId],
    queryFn: () => api.ragSearch({ query: submitted, examId, sheetId, topK: compact ? 3 : 6 }),
    enabled: submitted.length > 0,
  });

  return (
    <div className="space-y-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(query.trim());
        }}
        className="flex gap-2"
      >
        <Input
          placeholder="Search rag_chunks…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button type="submit" size="icon" disabled={!query.trim()}>
          {isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        </Button>
      </form>
      <div className="space-y-2">
        {data?.length === 0 && submitted && (
          <p className="text-sm text-muted-foreground">No chunks matched.</p>
        )}
        {data?.map((hit) => (
          <ChunkPreview
            key={hit.chunkId}
            text={hit.text}
            page={hit.page}
            region={hit.region}
            score={hit.score}
          />
        ))}
      </div>
    </div>
  );
}