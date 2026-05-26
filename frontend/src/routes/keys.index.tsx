import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { KeyRound, Plus } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { listExams } from "@/lib/api";

export const Route = createFileRoute("/keys/")({
  component: KeysList,
  head: () => ({
    meta: [
      { title: "Answer keys · GRADE" },
      { name: "description", content: "Browse exams, view answer-key counts, and open per-exam details." },
    ],
  }),
});

function KeysList() {
  const q = useQuery({ queryKey: ["exams"], queryFn: listExams, retry: 0 });
  const exams = q.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Exams"
        title="Answer keys"
        description="Every exam_id binds answer keys to student sheets and RAG corpora."
        actions={
          <Button asChild>
            <Link to="/keys/new"><Plus className="mr-2 h-4 w-4" /> New key</Link>
          </Button>
        }
      />
      {q.isLoading && <div className="text-sm text-muted-foreground">Loading…</div>}
      {q.isError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {(q.error as Error).message}
        </div>
      )}
      {!q.isLoading && exams.length === 0 && !q.isError && (
        <EmptyState
          icon={<KeyRound className="h-8 w-8" />}
          title="No exams yet"
          description="Upload an answer key — JSON or PDF — to create your first exam."
          action={<Button asChild><Link to="/keys/new">Create key</Link></Button>}
        />
      )}
      {exams.length > 0 && (
        <Card className="glass-card">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Exam id</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead className="text-right">Keys</TableHead>
                  <TableHead className="text-right">Sheets</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {exams.map((e) => (
                  <TableRow key={e.exam_id}>
                    <TableCell className="font-mono text-xs">{e.exam_id}</TableCell>
                    <TableCell>{e.title ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Badge variant="outline">{e.key_count}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant="outline">{e.sheet_count}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{e.updated_at ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link to="/keys/$examId" params={{ examId: e.exam_id }}>Open</Link>
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
