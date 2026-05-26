import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { listExams, uploadSheet, slugifyExamId } from "@/lib/api";

export const Route = createFileRoute("/sheets/new")({
  component: NewSheet,
  head: () => ({
    meta: [
      { title: "Upload sheet · GRADE" },
      { name: "description", content: "Upload a scanned student sheet — exam_id is required." },
    ],
  }),
});

function NewSheet() {
  const navigate = useNavigate();
  const exams = useQuery({ queryKey: ["exams"], queryFn: listExams, retry: 0 });
  const [examId, setExamId] = useState("");
  const [newExamId, setNewExamId] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const m = useMutation({
    mutationFn: () => {
      const id = examId === "__new__" ? slugifyExamId(newExamId) : examId;
      if (!id) throw new Error("Select or enter an exam_id.");
      if (!file) throw new Error("Pick a sheet file.");
      return uploadSheet({ file, exam_id: id });
    },
    onSuccess: (s) => {
      toast.success("Sheet uploaded");
      navigate({ to: "/sheets/$sheetId", params: { sheetId: s.sheet_id } });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <>
      <PageHeader
        eyebrow="Sheets"
        title="Upload student sheet"
        description="Sheets must reference an exam_id. The server creates per-sheet RAG chunks under sheet_{sheet_id}."
      />
      <SystemStatusPanel variant="compact" />
      <Card className="glass-card">
        <CardHeader>
          <CardTitle className="text-base">Sheet upload</CardTitle>
          <CardDescription>PDF or image. Pick an existing exam or create a new one inline.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              m.mutate();
            }}
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Exam</Label>
                <Select value={examId} onValueChange={setExamId}>
                  <SelectTrigger><SelectValue placeholder="Select exam_id" /></SelectTrigger>
                  <SelectContent>
                    {(exams.data ?? []).map((e) => (
                      <SelectItem key={e.exam_id} value={e.exam_id}>
                        {e.title ? `${e.title} · ${e.exam_id}` : e.exam_id}
                      </SelectItem>
                    ))}
                    <SelectItem value="__new__">+ Create new exam_id</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {examId === "__new__" && (
                <div className="space-y-1.5">
                  <Label htmlFor="newId">New exam_id</Label>
                  <Input id="newId" value={newExamId} onChange={(e) => setNewExamId(e.target.value)} placeholder="my-exam-2026" />
                </div>
              )}
              <div className="space-y-1.5 md:col-span-2">
                <Label htmlFor="sheet">Sheet file</Label>
                <Input id="sheet" type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              </div>
            </div>
            <Button type="submit" disabled={m.isPending}>
              <Upload className="mr-2 h-4 w-4" /> {m.isPending ? "Uploading…" : "Upload sheet"}
            </Button>
            {m.isError && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {(m.error as Error).message}
              </div>
            )}
          </form>
        </CardContent>
      </Card>
    </>
  );
}
