import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { listResults } from "@/lib/api";

export const Route = createFileRoute("/results/")({
  component: ResultsList,
  head: () => ({
    meta: [
      { title: "Results · GRADE" },
      { name: "description", content: "All persisted evaluation results — per-question rubrics and PDF exports." },
    ],
  }),
});

function ResultsList() {
  const q = useQuery({ queryKey: ["results"], queryFn: listResults, retry: 0 });
  const results = q.data ?? [];
  return (
    <>
      <PageHeader eyebrow="Evaluations" title="Results" description="Results persisted via insert_evaluation_result." />
      {q.isError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {(q.error as Error).message}
        </div>
      )}
      {!q.isLoading && results.length === 0 && !q.isError && (
        <EmptyState
          icon={<ClipboardCheck className="h-8 w-8" />}
          title="No results yet"
          description="Run an evaluation to populate this list."
          action={<Button asChild><Link to="/evaluate">Open evaluator</Link></Button>}
        />
      )}
      {results.length > 0 && (
        <Card className="glass-card">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Result</TableHead>
                  <TableHead>Exam</TableHead>
                  <TableHead>Sheet</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                  <TableHead>LLM</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {results.map((r) => (
                  <TableRow key={r.result_id}>
                    <TableCell className="font-mono text-xs">{r.result_id.slice(0, 10)}</TableCell>
                    <TableCell className="font-mono text-xs">{r.exam_id}</TableCell>
                    <TableCell className="font-mono text-xs">{r.sheet_id.slice(0, 10)}</TableCell>
                    <TableCell className="text-right font-mono">
                      {r.total_awarded.toFixed(1)} / {r.total_max}
                    </TableCell>
                    <TableCell>
                      <Badge variant={r.used_llm ? "default" : "outline"}>
                        {r.used_llm ? "Gemini" : "fallback"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link to="/results/$id" params={{ id: r.result_id }}>Open</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </>
  );
}
