import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/EmptyState";
import { FileScan, Plus } from "lucide-react";
import SheetDetail from "./SheetDetail";

export default function Sheets() {
  const { sheetId } = useParams();
  if (sheetId === "new") return null; // routed to SheetNew via App.tsx
  if (sheetId) return <SheetDetail sheetId={sheetId} />;

  const { data, isLoading } = useQuery({ queryKey: ["sheets"], queryFn: () => api.listSheets() });
  const { data: exams } = useQuery({ queryKey: ["exams"], queryFn: api.listExams });

  const examTitle = (id: string | null) =>
    id ? exams?.find((e) => e.id === id)?.title ?? id : "—";

  return (
    <div>
      <PageHeader
        title="Sheets"
        description="Scanned answer sheets ingested into pgvector for retrieval and grading."
        actions={
          <Button asChild>
            <Link to="/sheets/new">
              <Plus className="mr-1 h-4 w-4" /> Upload sheet
            </Link>
          </Button>
        }
      />
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={FileScan}
          title="No sheets yet"
          description="Upload a scanned answer sheet and link it to an exam."
          action={
            <Button asChild>
              <Link to="/sheets/new">Upload sheet</Link>
            </Button>
          }
        />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Filename</TableHead>
                <TableHead>Exam</TableHead>
                <TableHead>OCR engine</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Uploaded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link to={`/sheets/${s.id}`} className="font-medium hover:underline">
                      {s.filename}
                    </Link>
                    <div className="text-xs text-muted-foreground">{s.id}</div>
                  </TableCell>
                  <TableCell className="text-sm">{examTitle(s.examId)}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="capitalize">{s.ocrEngine}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="capitalize">{s.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">
                    {new Date(s.createdAt).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}