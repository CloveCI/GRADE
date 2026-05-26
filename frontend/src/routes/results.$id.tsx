import { createFileRoute } from "@tanstack/react-router";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { RubricBars } from "@/components/RubricBars";
import { getReportPdfUrl, getResult } from "@/lib/api";

export const Route = createFileRoute("/results/$id")({
  component: ResultDetail,
  head: ({ params }) => ({
    meta: [
      { title: `Result ${params.id.slice(0, 8)} · GRADE` },
      { name: "description", content: "Per-question rubric breakdown, OCR text, RAG flags, and PDF export." },
    ],
  }),
});

function ResultDetail() {
  const { id } = Route.useParams();
  const q = useQuery({ queryKey: ["result", id], queryFn: () => getResult(id), retry: 0 });
  const r = q.data;
  const pdfDisabled = !r || r.client_only;
  const duplicateQuestionIds = useMemo(() => {
    if (!r?.questions.length) return false;
    const ids = r.questions.map((q) => q.question_id);
    return new Set(ids).size < ids.length;
  }, [r?.questions]);

  return (
    <>
      <PageHeader
        eyebrow="Result"
        title={r ? `${r.total_awarded.toFixed(1)} / ${r.total_max}` : "Loading…"}
        description={r ? `exam ${r.exam_id} · sheet ${r.sheet_id.slice(0, 12)} · ${r.questions.length} questions` : undefined}
        actions={
          <Button asChild variant="outline" disabled={pdfDisabled}>
            <a href={pdfDisabled ? undefined : getReportPdfUrl(id)} target="_blank" rel="noreferrer">
              <FileText className="mr-2 h-4 w-4" /> Download PDF
            </a>
          </Button>
        }
      />
      {q.isError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {(q.error as Error).message}
        </div>
      )}
      {r && (
        <>
          {r.notes && (
            <Card className="glass-card">
              <CardContent className="py-3 text-sm text-muted-foreground">{r.notes}</CardContent>
            </Card>
          )}
          <Card className="glass-card">
            <CardHeader>
              <CardTitle className="text-base">Question breakdown</CardTitle>
              <CardDescription>RAG-grounded scoring with rubric criteria.</CardDescription>
            </CardHeader>
            <CardContent>
              <Accordion type="multiple">
                {r.questions.map((qn, idx) => {
                  const itemKey = `${id}-q-${idx}`;
                  const label = duplicateQuestionIds
                    ? `${qn.question_id} · patch ${idx + 1}`
                    : qn.question_id;
                  return (
                  <AccordionItem key={itemKey} value={itemKey}>
                    <AccordionTrigger className="text-sm">
                      <div className="flex w-full items-center justify-between gap-3 pr-3">
                        <span className="font-mono text-xs text-muted-foreground">{label}</span>
                        <span className="truncate text-left">
                          {duplicateQuestionIds
                            ? `OCR patch ${idx + 1}`
                            : (qn.question_text || qn.question_id || "—")}
                        </span>
                        <div className="flex items-center gap-2">
                          {qn.flags?.rag_context_used && <Badge variant="outline" className="border-primary/40 text-primary">RAG</Badge>}
                          <ConfidenceBadge value={qn.confidence} />
                          <span className="font-mono">{qn.awarded_marks.toFixed(1)} / {qn.max_marks}</span>
                        </div>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="space-y-3">
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <div>
                          <div className="kpi-label mb-1">Expected</div>
                          <p className="text-sm text-foreground/90">{qn.expected_answer ?? "—"}</p>
                        </div>
                        <div>
                          <div className="kpi-label mb-1">Student answer (formatted)</div>
                          <p className="text-sm text-foreground/90">{qn.student_answer ?? "—"}</p>
                        </div>
                      </div>
                      {qn.ocr_raw && qn.ocr_raw.trim() !== (qn.student_answer ?? "").trim() && (
                        <div>
                          <div className="kpi-label mb-1">Raw OCR (before cleanup)</div>
                          <pre className="overflow-x-auto rounded-md border border-border/60 bg-muted/40 p-2 text-xs text-muted-foreground">
{qn.ocr_raw}
                          </pre>
                        </div>
                      )}
                      {qn.ocr_text && (!qn.ocr_raw || qn.ocr_raw === qn.student_answer) && (
                        <div>
                          <div className="kpi-label mb-1">OCR text</div>
                          <pre className="overflow-x-auto rounded-md border border-border/60 bg-muted/40 p-2 text-xs">
{qn.ocr_text}
                          </pre>
                        </div>
                      )}
                      <div>
                        <div className="kpi-label mb-2">Rubric</div>
                        <RubricBars rubric={qn.rubric} />
                      </div>
                      {qn.rationale && (
                        <div className="rounded-md border border-border/60 bg-card/40 p-3 text-xs text-muted-foreground">
                          {qn.rationale}
                        </div>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                  );
                })}
              </Accordion>
            </CardContent>
          </Card>
        </>
      )}
    </>
  );
}
