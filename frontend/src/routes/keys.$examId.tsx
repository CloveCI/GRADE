import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { PlayCircle, RefreshCcw, FileScan } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { VectorPreview } from "@/components/VectorPreview";
import { RagSearchPanel } from "@/components/RagSearchPanel";
import { getExam, ingestExamRag } from "@/lib/api";

export const Route = createFileRoute("/keys/$examId")({
  component: KeyDetail,
  head: ({ params }) => ({
    meta: [
      { title: `Key ${params.examId} · GRADE` },
      { name: "description", content: `Answer key questions, RAG status, and linked sheets for exam ${params.examId}.` },
    ],
  }),
});

function KeyDetail() {
  const { examId } = Route.useParams();
  const q = useQuery({ queryKey: ["exam", examId], queryFn: () => getExam(examId), retry: 0 });
  const reindex = useMutation({
    mutationFn: () => ingestExamRag(examId),
    onSuccess: (d) => toast.success(`Re-indexed — ${d.chunks} chunks`),
    onError: (e: Error) => toast.error(e.message),
  });

  const exam = q.data?.exam;
  const keys = q.data?.keys;
  const sheets = q.data?.sheets ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Answer key"
        title={exam?.title || examId}
        description={`exam_id: ${examId}`}
        actions={
          <>
            <Button variant="outline" onClick={() => reindex.mutate()} disabled={reindex.isPending}>
              <RefreshCcw className="mr-2 h-4 w-4" /> {reindex.isPending ? "Re-indexing…" : "Re-index RAG"}
            </Button>
            <Button asChild>
              <Link to="/evaluate" search={{ exam: examId } as any}>
                <PlayCircle className="mr-2 h-4 w-4" /> Evaluate
              </Link>
            </Button>
          </>
        }
      />
      {q.isError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {(q.error as Error).message}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="glass-card lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Questions</CardTitle>
            <CardDescription>{keys?.questions.length ?? 0} questions in this key.</CardDescription>
          </CardHeader>
          <CardContent>
            <Accordion type="single" collapsible>
              {(keys?.questions ?? []).map((qn, i) => (
                <AccordionItem key={`${examId}-${qn.question_id}-${i}`} value={`${examId}-${qn.question_id}-${i}`}>
                  <AccordionTrigger className="text-sm">
                    <div className="flex w-full items-center justify-between gap-3 pr-3">
                      <span className="font-mono text-xs text-muted-foreground">{qn.question_id}</span>
                      <span className="truncate">{qn.question_text ?? "(no text)"}</span>
                      <Badge variant="outline">{qn.max_marks ?? "?"} pts</Badge>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="space-y-3">
                    {qn.expected_answer && (
                      <div>
                        <div className="kpi-label mb-1">Expected</div>
                        <p className="text-sm text-foreground/90">{qn.expected_answer}</p>
                      </div>
                    )}
                    {qn.rubric && (
                      <div>
                        <div className="kpi-label mb-1">Rubric</div>
                        <p className="text-xs text-muted-foreground">{qn.rubric}</p>
                      </div>
                    )}
                    <div>
                      <div className="kpi-label mb-1">Vector preview</div>
                      <VectorPreview vector={Array.from({ length: 48 }, (_, i) => Math.sin(i / 3 + qn.question_id.length))} />
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card className="glass-card">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <FileScan className="h-4 w-4 text-primary" /> Linked sheets
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {sheets.length === 0 && <div className="text-xs text-muted-foreground">No sheets yet.</div>}
              {sheets.map((s) => (
                <Link
                  key={s.sheet_id}
                  to="/sheets/$sheetId"
                  params={{ sheetId: s.sheet_id }}
                  className="flex items-center justify-between rounded-md border border-border/60 bg-card/40 p-2 text-xs hover:border-primary/40"
                >
                  <span className="font-mono">{s.sheet_id.slice(0, 12)}</span>
                  <span className="text-muted-foreground">{s.filename ?? ""}</span>
                </Link>
              ))}
            </CardContent>
          </Card>
          <RagSearchPanel examId={examId} />
        </div>
      </div>
    </>
  );
}
