import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { FileScan, Plus } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { listSheets } from "@/lib/api";

export const Route = createFileRoute("/sheets/")({
  component: SheetsList,
  head: () => ({
    meta: [
      { title: "Sheets · GRADE" },
      { name: "description", content: "All scanned student response sheets indexed in PostgreSQL + pgvector." },
    ],
  }),
});

function SheetsList() {
  const q = useQuery({ queryKey: ["sheets"], queryFn: listSheets, retry: 0 });
  const sheets = q.data ?? [];
  return (
    <>
      <PageHeader
        eyebrow="Sheets"
        title="Student sheets"
        description="Each sheet is bound to an exam_id and indexed as its own RAG corpus."
        actions={<Button asChild><Link to="/sheets/new"><Plus className="mr-2 h-4 w-4" /> Upload sheet</Link></Button>}
      />
      {q.isError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {(q.error as Error).message}
        </div>
      )}
      {!q.isLoading && sheets.length === 0 && !q.isError && (
        <EmptyState
          icon={<FileScan className="h-8 w-8" />}
          title="No sheets uploaded"
          description="Upload a PDF or image — exam_id is required."
          action={<Button asChild><Link to="/sheets/new">Upload sheet</Link></Button>}
        />
      )}
      {sheets.length > 0 && (
        <Card className="glass-card">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sheet id</TableHead>
                  <TableHead>Exam</TableHead>
                  <TableHead>Filename</TableHead>
                  <TableHead className="text-right">Pages</TableHead>
                  <TableHead>Ingested</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sheets.map((s) => (
                  <TableRow key={s.sheet_id}>
                    <TableCell className="font-mono text-xs">{s.sheet_id.slice(0, 12)}</TableCell>
                    <TableCell className="font-mono text-xs">{s.exam_id}</TableCell>
                    <TableCell className="text-sm">{s.filename ?? "—"}</TableCell>
                    <TableCell className="text-right">{s.pages ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant={s.ingested ? "default" : "outline"}>
                        {s.ingested ? "yes" : "pending"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="ghost">
                        <Link to="/sheets/$sheetId" params={{ sheetId: s.sheet_id }}>Open</Link>
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
