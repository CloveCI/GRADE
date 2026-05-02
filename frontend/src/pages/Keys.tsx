import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/EmptyState";
import { KeyRound, Plus } from "lucide-react";
import KeyDetail from "./KeyDetail";

export default function Keys() {
  const { examId } = useParams();
  if (examId) return <KeyDetail examId={examId} />;

  const { data, isLoading } = useQuery({
    queryKey: ["exams-with-counts"],
    queryFn: api.listExamsWithCounts,
  });

  return (
    <div>
      <PageHeader
        title="Keys"
        description="Answer keys grouped by exam. Each exam links to its uploaded sheets."
        actions={
          <Button asChild>
            <Link to="/keys/new">
              <Plus className="mr-1 h-4 w-4" /> New keys
            </Link>
          </Button>
        }
      />
      {isLoading ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            Loading exams…
          </CardContent>
        </Card>
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={KeyRound}
          title="No keys yet"
          description="Upload an answer key to start grading sheets."
          action={
            <Button asChild>
              <Link to="/keys/new">Upload keys</Link>
            </Button>
          }
        />
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Exam</TableHead>
                <TableHead className="w-24 text-right">Keys</TableHead>
                <TableHead className="w-24 text-right">Sheets</TableHead>
                <TableHead className="w-44">Last evaluation</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((row) => (
                <TableRow key={row.examId} className="cursor-pointer">
                  <TableCell>
                    <Link to={`/keys/${row.examId}`} className="font-medium text-foreground hover:underline">
                      {row.title}
                    </Link>
                    <div className="text-xs text-muted-foreground">{row.examId}</div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant="secondary">{row.keyCount}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant="outline">{row.sheetCount}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {row.lastEvalAt ? new Date(row.lastEvalAt).toLocaleString() : "—"}
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