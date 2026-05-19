import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { VectorPreview } from "@/components/VectorPreview";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Database, FileScan, PlayCircle } from "lucide-react";
import { toast } from "sonner";

export default function KeyDetail({ examId }: { examId: string }) {
  const reindex = useMutation({
    mutationFn: () => api.ingestExamRag(examId),
    onSuccess: () => toast.success("Answer keys re-indexed into RAG"),
    onError: (e: Error) => toast.error(e.message),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["exam", examId],
    queryFn: () => api.getExam(examId),
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (!data) return <p className="text-sm text-destructive">Exam not found.</p>;

  const { exam, keys, sheets } = data;

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/keys">
          <ArrowLeft className="mr-1 h-4 w-4" /> All exams
        </Link>
      </Button>
      <PageHeader
        title={exam.title}
        description={`Exam ID: ${exam.id} · ${keys.length} key${keys.length === 1 ? "" : "s"}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => reindex.mutate()} disabled={reindex.isPending}>
              <Database className="mr-1 h-4 w-4" />
              Re-index keys RAG
            </Button>
            {sheets[0] ? (
              <Button asChild>
                <Link to={`/evaluate/${sheets[0].id}?exam=${exam.id}`}>
                  <PlayCircle className="mr-1 h-4 w-4" /> Evaluate first sheet
                </Link>
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Questions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {keys.map((k) => (
              <div key={k.id} className="rounded-md border bg-card p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{k.questionId}</Badge>
                    <span className="text-sm font-medium text-foreground">{k.prompt}</span>
                  </div>
                  <Badge variant="secondary">{k.maxMarks} pts</Badge>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{k.answer}</p>
                <div className="mt-3 flex items-center gap-3">
                  <span className="text-xs uppercase tracking-wider text-muted-foreground">
                    vector
                  </span>
                  <VectorPreview vector={k.vector} className="flex-1" />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle className="text-base">Linked sheets</CardTitle>
            <Badge variant="outline">{sheets.length}</Badge>
          </CardHeader>
          <CardContent className="space-y-2">
            {sheets.length === 0 && (
              <p className="text-sm text-muted-foreground">No sheets uploaded yet for this exam.</p>
            )}
            {sheets.map((s) => (
              <Link
                key={s.id}
                to={`/sheets/${s.id}`}
                className="flex items-center justify-between rounded-md border bg-card p-3 hover:bg-muted/40"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FileScan className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate text-sm">{s.filename}</span>
                </div>
                <Badge variant="outline" className="capitalize">{s.status}</Badge>
              </Link>
            ))}
            <Button asChild variant="outline" size="sm" className="w-full">
              <Link to={`/sheets/new?exam=${exam.id}`}>Upload sheet for this exam</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}