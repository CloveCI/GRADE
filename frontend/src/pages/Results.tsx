import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@/components/ui/accordion";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { RubricBars } from "@/components/RubricBars";
import { ChunkPreview } from "@/components/ChunkPreview";
import { EmptyState } from "@/components/EmptyState";
import { ArrowLeft, ClipboardList, Download } from "lucide-react";
import { toast } from "sonner";
import type { EvaluationResult } from "@/lib/types";

const RAW = import.meta.env.VITE_API_URL as string | undefined;
const API_BASE = (RAW ?? "").replace(/\/$/, "");

function ResultDetail({ resultId }: { resultId: string }) {
  const location = useLocation();
  const fromNav = (location.state as { evaluationResult?: EvaluationResult } | null)?.evaluationResult;
  const seed = fromNav?.id === resultId ? fromNav : undefined;
  const shouldFetchServer = !seed;

  const { data: fetched, isFetching, isFetched } = useQuery({
    queryKey: ["result", resultId],
    queryFn: () => api.getResult(resultId),
    enabled: shouldFetchServer,
  });

  const result = fetched ?? seed ?? null;
  /** Timeline-only result passed via router state; nothing persisted under GET /result/… */
  const clientPreviewOnly = Boolean(seed);

  const { data: sheet } = useQuery({
    queryKey: ["sheet", result?.sheetId],
    queryFn: () => api.getSheet(result!.sheetId),
    enabled: !!result?.sheetId,
  });
  const { data: chunks } = useQuery({
    queryKey: ["sheet-chunks", result?.sheetId],
    queryFn: () => api.getSheetChunks(result!.sheetId),
    enabled: !!result?.sheetId,
  });

  if (shouldFetchServer && isFetching) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (shouldFetchServer && isFetched && fetched == null) {
    return (
      <EmptyState
        icon={ClipboardList}
        title="Result not found"
        description="This evaluation ID is not on the server. Open it from Evaluate after a run, or pick a result from the list."
      />
    );
  }
  if (!result) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const pct = (result.totalMarks / result.maxTotal) * 100;

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/results"><ArrowLeft className="mr-1 h-4 w-4" /> All results</Link>
      </Button>
      <PageHeader
        title={`Result ${result.id}`}
        description={`${sheet?.filename ?? result.sheetId} · ${result.examId}`}
        actions={
          <Button
            variant="outline"
            disabled={clientPreviewOnly}
            title={
              clientPreviewOnly
                ? "PDF is generated on the server after a real evaluation. This run was a local preview only."
                : undefined
            }
            onClick={() => {
              const url = `${API_BASE}/report/${encodeURIComponent(result.id)}/pdf`;
              window.open(url, "_blank", "noopener,noreferrer");
              toast.success("Opening PDF report");
            }}
          >
            <Download className="mr-1 h-4 w-4" /> PDF
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-4">
        <Card><CardContent className="p-4">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">Total</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">
            {result.totalMarks} <span className="text-base text-muted-foreground">/ {result.maxTotal}</span>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">{pct.toFixed(0)}%</div>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">Confidence</div>
          <div className="mt-2"><ConfidenceBadge value={result.gradingConfidence} flag={result.confidenceFlag} /></div>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">Model</div>
          <div className="mt-1 text-sm font-medium">{result.model}</div>
          <div className="text-xs text-muted-foreground">prompt {result.promptHash}</div>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">When</div>
          <div className="mt-1 text-sm">{new Date(result.createdAt).toLocaleString()}</div>
        </CardContent></Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader><CardTitle className="text-base">Per-question breakdown</CardTitle></CardHeader>
          <CardContent>
            <Accordion type="multiple" className="w-full">
              {result.questions.map((q, i) => {
                const qpct = (q.awarded / q.max) * 100;
                const itemKey = `${result.id}-${i}-${q.questionId}`;
                return (
                  <AccordionItem key={itemKey} value={itemKey}>
                    <AccordionTrigger>
                      <div className="flex flex-1 items-center gap-3 pr-3">
                        <Badge variant="outline">{q.questionId}</Badge>
                        <div className="flex-1 text-left text-sm font-medium">{q.feedback.slice(0, 60)}…</div>
                        <span className="tabular-nums text-sm">{q.awarded}/{q.max}</span>
                        <ConfidenceBadge value={q.ocrConfidence} />
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-3">
                        <div className="rounded-md border bg-muted/30 p-3 text-sm">
                          <div className="text-xs uppercase tracking-wider text-muted-foreground">OCR text</div>
                          <p className="mt-1">{q.ocrText}</p>
                        </div>
                        <RubricBars rubric={q.rubric} />
                        <div className="text-xs uppercase tracking-wider text-muted-foreground">Awarded {qpct.toFixed(0)}%</div>
                        <p className="text-sm text-foreground">{q.feedback}</p>
                        {q.flags.length > 0 && (
                          <div className="flex gap-1">
                            {q.flags.map((f) => <Badge key={f} variant="destructive">{f}</Badge>)}
                          </div>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader><CardTitle className="text-base">Sheet chunks</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {chunks?.map((c) => (
              <ChunkPreview
                key={c.id}
                text={c.text}
                page={c.page}
                region={c.region}
                confidence={c.ocrConfidence}
                highlighted={result.questions.some((q) => q.matchedChunkId === c.id)}
              />
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function Results() {
  const { resultId } = useParams();
  if (resultId) return <ResultDetail resultId={resultId} />;

  const [examFilter, setExamFilter] = useState<string>("all");
  const { data: exams } = useQuery({ queryKey: ["exams"], queryFn: api.listExams });
  const { data, isLoading } = useQuery({
    queryKey: ["results", examFilter],
    queryFn: () => api.listResults(examFilter !== "all" ? { examId: examFilter } : undefined),
  });

  return (
    <div>
      <PageHeader
        title="Saved evaluations"
        description="Every graded sheet with rubric, confidence, and matched chunks."
        actions={
          <Select value={examFilter} onValueChange={setExamFilter}>
            <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All exams</SelectItem>
              {exams?.map((e) => <SelectItem key={e.id} value={e.id}>{e.title}</SelectItem>)}
            </SelectContent>
          </Select>
        }
      />
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={ClipboardList}
          title="No evaluations yet"
          description="Run an evaluation from the Evaluate portal to see results here."
        />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Result</TableHead>
                <TableHead>Exam</TableHead>
                <TableHead>Sheet</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead className="text-right">When</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>
                    <Link to={`/results/${r.id}`} className="font-medium hover:underline">{r.id}</Link>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{r.examId}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{r.sheetId}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.totalMarks} / {r.maxTotal}</TableCell>
                  <TableCell><ConfidenceBadge value={r.gradingConfidence} flag={r.confidenceFlag} /></TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">{new Date(r.createdAt).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}