import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { RagSearchPanel } from "@/components/RagSearchPanel";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { listExams, listSheets } from "@/lib/api";

export const Route = createFileRoute("/rag")({
  component: RagExplorer,
  head: () => ({
    meta: [
      { title: "RAG Explorer · GRADE" },
      { name: "description", content: "Query hybrid RAG across answer-key and sheet corpora in pgvector." },
    ],
  }),
});

function RagExplorer() {
  const exams = useQuery({ queryKey: ["exams"], queryFn: listExams, retry: 0 });
  const sheets = useQuery({ queryKey: ["sheets"], queryFn: listSheets, retry: 0 });
  const [examId, setExamId] = useState<string>("");
  const [sheetId, setSheetId] = useState<string>("");

  const filteredSheets = (sheets.data ?? []).filter((s) => !examId || s.exam_id === examId);

  return (
    <>
      <PageHeader
        eyebrow="Tools"
        title="RAG Explorer"
        description="Search keys_{exam_id} and sheet_{sheet_id} corpora. Combine both for hybrid retrieval."
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="text-base">Scope</CardTitle>
            <CardDescription>Limit retrieval to specific corpora.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <Label>Exam</Label>
              <Select
                value={examId || "__any__"}
                onValueChange={(v) => { setExamId(v === "__any__" ? "" : v); setSheetId(""); }}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__any__">Any exam</SelectItem>
                  {(exams.data ?? []).map((e) => (
                    <SelectItem key={e.exam_id} value={e.exam_id}>
                      {e.title ? `${e.title} · ${e.exam_id}` : e.exam_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Sheet (optional)</Label>
              <Select
                value={sheetId || "__none__"}
                onValueChange={(v) => setSheetId(v === "__none__" ? "" : v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">No sheet</SelectItem>
                  {filteredSheets.map((s) => (
                    <SelectItem key={s.sheet_id} value={s.sheet_id}>
                      {s.filename ?? s.sheet_id.slice(0, 12)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
        <div className="lg:col-span-2">
          <RagSearchPanel examId={examId || undefined} sheetId={sheetId || undefined} />
        </div>
      </div>
    </>
  );
}
