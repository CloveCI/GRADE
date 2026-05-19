import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChunkPreview } from "@/components/ChunkPreview";
import { RagSearchPanel } from "@/components/RagSearchPanel";
import { ArrowLeft, FileScan, PlayCircle, RefreshCw, Database } from "lucide-react";
import { toast } from "sonner";

export default function SheetDetail({ sheetId }: { sheetId: string }) {
  const queryClient = useQueryClient();
  const { data: sheet } = useQuery({ queryKey: ["sheet", sheetId], queryFn: () => api.getSheet(sheetId) });
  const { data: chunks } = useQuery({ queryKey: ["sheet-chunks", sheetId], queryFn: () => api.getSheetChunks(sheetId) });
  const ingest = useMutation({
    mutationFn: () => api.ingestSheet(sheetId, true),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["sheet-chunks", sheetId] });
      toast.success(`RAG ingest: ${String(res.status ?? "done")} (${res.chunks_saved ?? "?"} chunks)`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const ingestExam = useMutation({
    mutationFn: () => {
      const ex = sheet?.examId;
      if (!ex) throw new Error("Sheet has no exam_id");
      return api.ingestExamRag(ex, sheetId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sheet-chunks", sheetId] });
      toast.success("Re-indexed keys + sheet RAG corpora");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!sheet) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/sheets">
          <ArrowLeft className="mr-1 h-4 w-4" /> All sheets
        </Link>
      </Button>
      <PageHeader
        title={sheet.filename}
        description={`${sheet.id} · ${sheet.pageCount} page${sheet.pageCount === 1 ? "" : "s"}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => ingest.mutate()} disabled={ingest.isPending}>
              <RefreshCw className={`mr-1 h-4 w-4 ${ingest.isPending ? "animate-spin" : ""}`} />
              Ingest sheet
            </Button>
            {sheet.examId ? (
              <Button
                variant="outline"
                onClick={() => ingestExam.mutate()}
                disabled={ingestExam.isPending}
              >
                <Database className={`mr-1 h-4 w-4 ${ingestExam.isPending ? "animate-pulse" : ""}`} />
                Re-index exam RAG
              </Button>
            ) : null}
            {sheet.examId ? (
              <Button asChild>
                <Link to={`/evaluate/${sheet.id}?exam=${sheet.examId}`}>
                  <PlayCircle className="mr-1 h-4 w-4" /> Evaluate
                </Link>
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Original file</CardTitle>
            </CardHeader>
            <CardContent>
              {sheet.fileUrl && sheet.mimeType?.startsWith("image/") ? (
                <img src={sheet.fileUrl} alt={sheet.filename} className="max-h-96 w-full object-contain rounded-md border bg-muted" />
              ) : sheet.fileUrl && sheet.mimeType === "application/pdf" ? (
                <iframe src={sheet.fileUrl} title={sheet.filename} className="h-96 w-full rounded-md border" />
              ) : (
                <div className="flex items-center justify-center gap-2 rounded-md border bg-muted/30 py-12 text-sm text-muted-foreground">
                  <FileScan className="h-5 w-5" /> No preview available (seed sheet).
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                {sheet.examId ? (
                  <Badge variant="secondary">exam: {sheet.examId}</Badge>
                ) : null}
                <Badge variant="outline">document_id: {sheet.documentId}</Badge>
                <Badge variant="outline" className="capitalize">engine: {sheet.ocrEngine}</Badge>
                <Badge variant="outline" className="capitalize">status: {sheet.status}</Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">RAG chunks ({chunks?.length ?? 0})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {chunks?.map((c) => (
                <ChunkPreview
                  key={c.id}
                  text={c.text}
                  page={c.page}
                  region={c.region}
                  confidence={c.ocrConfidence}
                />
              ))}
            </CardContent>
          </Card>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">Search this sheet</CardTitle>
          </CardHeader>
          <CardContent>
            <RagSearchPanel sheetId={sheet.id} examId={sheet.examId ?? undefined} compact />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}