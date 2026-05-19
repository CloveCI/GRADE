import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Upload, FileKey, FileScan } from "lucide-react";
import { toast } from "sonner";

export default function UploadBundle() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: exams } = useQuery({ queryKey: ["exams"], queryFn: api.listExams });
  const { data: integrations } = useQuery({
    queryKey: ["integrations"],
    queryFn: () => api.integrations(),
    staleTime: 60_000,
  });

  const [examMode, setExamMode] = useState<"existing" | "new">("new");
  const [examId, setExamId] = useState("");
  const [newExamTitle, setNewExamTitle] = useState("");
  const [keyFile, setKeyFile] = useState<File | null>(null);
  const [sheetFile, setSheetFile] = useState<File | null>(null);
  const [defaultMaxMarks, setDefaultMaxMarks] = useState("4");

  const upload = useMutation({
    mutationFn: async () => {
      let targetExamId = examId;
      if (examMode === "new") {
        if (!newExamTitle.trim()) throw new Error("Enter an exam title or id");
        const exam = await api.createExam(newExamTitle.trim());
        targetExamId = exam.id;
      }
      if (!targetExamId) throw new Error("Pick or create an exam");
      if (!keyFile) throw new Error("Pick an answer key file (.json or .pdf)");
      if (!sheetFile) throw new Error("Pick an answer sheet (PDF or image)");
      return api.uploadExamBundle({
        examId: targetExamId,
        keyFile,
        sheetFile,
        defaultMaxMarks: Number(defaultMaxMarks) || 4,
      });
    },
    onSuccess: (out) => {
      qc.invalidateQueries({ queryKey: ["exams"] });
      qc.invalidateQueries({ queryKey: ["exams-with-counts"] });
      qc.invalidateQueries({ queryKey: ["sheets"] });
      qc.invalidateQueries({ queryKey: ["exam", out.examId] });
      toast.success("Exam bundle uploaded and indexed for RAG");
      navigate(`/evaluate/${out.sheetId}?exam=${encodeURIComponent(out.examId)}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const llm = integrations?.llm_gemini;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Upload exam bundle"
        description="Upload answer key + sheet together under one exam_id. Both are stored and indexed for joint RAG retrieval during grading."
      />

      {llm && !llm.ready ? (
        <Alert>
          <AlertTitle>Gemini optional</AlertTitle>
          <AlertDescription className="text-sm">
            Upload works without Gemini. For LLM grading, set{" "}
            <code className="rounded bg-muted px-1">GRADE_ENABLE_LLM</code> and{" "}
            <code className="rounded bg-muted px-1">GRADE_GEMINI_API_KEY</code> in the API{" "}
            <code className="rounded bg-muted px-1">.env</code> and restart uvicorn.
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Exam</CardTitle>
          <CardDescription>Keys and sheet must share this id.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Button
              type="button"
              variant={examMode === "new" ? "default" : "outline"}
              size="sm"
              onClick={() => setExamMode("new")}
            >
              New exam
            </Button>
            <Button
              type="button"
              variant={examMode === "existing" ? "default" : "outline"}
              size="sm"
              onClick={() => setExamMode("existing")}
            >
              Existing exam
            </Button>
          </div>
          {examMode === "new" ? (
            <Input
              placeholder="Exam title (slug id is generated, e.g. physics-101-final)"
              value={newExamTitle}
              onChange={(e) => setNewExamTitle(e.target.value)}
            />
          ) : (
            <Select value={examId} onValueChange={setExamId}>
              <SelectTrigger>
                <SelectValue placeholder="Select exam" />
              </SelectTrigger>
              <SelectContent>
                {exams?.map((e) => (
                  <SelectItem key={e.id} value={e.id}>
                    {e.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileKey className="h-4 w-4" /> Answer key
            </CardTitle>
          </CardHeader>
          <CardContent>
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-md border border-dashed px-4 py-8 text-sm text-muted-foreground hover:bg-muted/30">
              <Upload className="h-5 w-5" />
              <span>{keyFile ? keyFile.name : "JSON or PDF"}</span>
              <input
                type="file"
                accept=".json,application/json,application/pdf,.pdf"
                className="hidden"
                onChange={(e) => setKeyFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileScan className="h-4 w-4" /> Answer sheet
            </CardTitle>
          </CardHeader>
          <CardContent>
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-md border border-dashed px-4 py-8 text-sm text-muted-foreground hover:bg-muted/30">
              <Upload className="h-5 w-5" />
              <span>{sheetFile ? sheetFile.name : "PDF or image"}</span>
              <input
                type="file"
                accept="application/pdf,image/*"
                className="hidden"
                onChange={(e) => setSheetFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="space-y-2">
            <Label htmlFor="default_marks">Default max marks (PDF keys)</Label>
            <Input
              id="default_marks"
              type="number"
              min={1}
              value={defaultMaxMarks}
              onChange={(e) => setDefaultMaxMarks(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" asChild>
          <Link to="/">Cancel</Link>
        </Button>
        <Button onClick={() => upload.mutate()} disabled={upload.isPending}>
          {upload.isPending ? "Uploading & indexing…" : "Upload bundle & go to Evaluate"}
        </Button>
      </div>
    </div>
  );
}
