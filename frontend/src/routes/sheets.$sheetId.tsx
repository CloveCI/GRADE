import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { PlayCircle, RefreshCcw, Layers } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChunkPreview } from "@/components/ChunkPreview";
import { RagSearchPanel } from "@/components/RagSearchPanel";
import { getSheetChunks, getSheetFileUrl, ingestSheet, ingestExamRag, listSheets } from "@/lib/api";

export const Route = createFileRoute("/sheets/$sheetId")({
  component: SheetDetail,
  head: ({ params }) => ({
    meta: [
      { title: `Sheet ${params.sheetId.slice(0, 8)} · GRADE` },
      { name: "description", content: "Sheet preview, RAG chunks, ingest controls, and evaluation shortcut." },
    ],
  }),
});

function SheetDetail() {
  const { sheetId } = Route.useParams();
  const sheets = useQuery({ queryKey: ["sheets"], queryFn: listSheets, retry: 0 });
  const sheet = (sheets.data ?? []).find((s) => s.sheet_id === sheetId);
  const examId = sheet?.exam_id;

  const chunksQ = useQuery({ queryKey: ["sheet-chunks", sheetId], queryFn: () => getSheetChunks(sheetId), retry: 0 });

  const ingestM = useMutation({
    mutationFn: () => ingestSheet(sheetId, true),
    onSuccess: (d) => toast.success(`Ingested ${d.chunks} chunks`),
    onError: (e: Error) => toast.error(e.message),
  });
  const reExamM = useMutation({
    mutationFn: () => ingestExamRag(examId!, sheetId),
    onSuccess: (d) => toast.success(`Exam RAG re-indexed (${d.chunks} chunks)`),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <>
      <PageHeader
        eyebrow="Sheet"
        title={sheet?.filename || sheetId}
        description={examId ? `exam_id: ${examId}` : "Loading sheet…"}
        actions={
          <>
            <Button variant="outline" onClick={() => ingestM.mutate()} disabled={ingestM.isPending}>
              <Layers className="mr-2 h-4 w-4" /> {ingestM.isPending ? "Ingesting…" : "Ingest sheet"}
            </Button>
            <Button variant="outline" onClick={() => reExamM.mutate()} disabled={!examId || reExamM.isPending}>
              <RefreshCcw className="mr-2 h-4 w-4" /> Re-index exam RAG
            </Button>
            <Button asChild disabled={!examId}>
              <Link to="/evaluate/$sheetId" params={{ sheetId }} search={{ exam: examId } as any}>
                <PlayCircle className="mr-2 h-4 w-4" /> Evaluate
              </Link>
            </Button>
          </>
        }
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="glass-card lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Preview</CardTitle>
            <CardDescription>Served from /sheet/{`{id}`}/file</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="aspect-[1/1.3] w-full overflow-hidden rounded-md border border-border/60 bg-muted">
              <iframe src={getSheetFileUrl(sheetId)} title="sheet preview" className="h-full w-full" />
            </div>
          </CardContent>
        </Card>
        <RagSearchPanel sheetId={sheetId} examId={examId} />
      </div>
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-base">RAG chunks</CardTitle>
          <CardDescription>{chunksQ.data?.length ?? 0} chunks indexed for this sheet.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {(chunksQ.data ?? []).map((c) => <ChunkPreview key={c.chunk_id} chunk={c} />)}
          {chunksQ.data?.length === 0 && (
            <div className="text-xs text-muted-foreground">No chunks — run “Ingest sheet”.</div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
