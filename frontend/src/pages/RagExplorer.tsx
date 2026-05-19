import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RagSearchPanel } from "@/components/RagSearchPanel";

export default function RagExplorer() {
  const { data: exams } = useQuery({ queryKey: ["exams"], queryFn: api.listExams });
  const { data: sheets } = useQuery({ queryKey: ["sheets"], queryFn: () => api.listSheets() });

  const [examId, setExamId] = useState<string>("");
  const [sheetId, setSheetId] = useState<string>("");

  const sheetsForExam = examId
    ? (sheets ?? []).filter((s) => s.examId === examId)
    : sheets ?? [];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="RAG Explorer"
        description="Hybrid search over keys_{exam_id} and sheet_{id} corpora. Scope by exam and optional sheet."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Scope</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Exam (recommended)</Label>
            <Select
              value={examId || "__all__"}
              onValueChange={(v) => {
                setExamId(v === "__all__" ? "" : v);
                setSheetId("");
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="All exams" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All exams</SelectItem>
                {exams?.map((e) => (
                  <SelectItem key={e.id} value={e.id}>
                    {e.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Sheet (optional)</Label>
            <Select
              value={sheetId || "__none__"}
              onValueChange={(v) => setSheetId(v === "__none__" ? "" : v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="No sheet scope" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">No sheet — exam-wide</SelectItem>
                {sheetsForExam.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Search</CardTitle>
        </CardHeader>
        <CardContent>
          <RagSearchPanel
            examId={examId || undefined}
            sheetId={sheetId || undefined}
          />
        </CardContent>
      </Card>
    </div>
  );
}
