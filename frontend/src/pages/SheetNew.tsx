import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Upload, FileScan } from "lucide-react";
import { toast } from "sonner";

export default function SheetNew() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const { data: exams } = useQuery({ queryKey: ["exams"], queryFn: api.listExams });

  const [examMode, setExamMode] = useState<"existing" | "new">(
    params.get("exam") ? "existing" : "new",
  );
  const [examId, setExamId] = useState<string>(params.get("exam") ?? "");
  const [newExamTitle, setNewExamTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const onPickFile = (f: File) => {
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(f));
  };

  const create = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Pick a file");
      let targetExamId = examId;
      if (examMode === "new") {
        if (!newExamTitle.trim()) throw new Error("Enter an exam title");
        const exam = await api.createExam(newExamTitle.trim());
        targetExamId = exam.id;
      }
      if (!targetExamId) throw new Error("Pick or create an exam");
      const sheet = await api.createSheet({
        filename: file.name,
        examId: targetExamId,
        file,
        pageCount: file.type === "application/pdf" ? 2 : 1,
      });
      return sheet;
    },
    onSuccess: (sheet) => {
      qc.invalidateQueries({ queryKey: ["sheets"] });
      qc.invalidateQueries({ queryKey: ["exams-with-counts"] });
      qc.invalidateQueries({ queryKey: ["exam", sheet.examId] });
      toast.success("Sheet ingested");
      navigate(`/sheets/${sheet.id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Upload sheet"
        description="Pick a scanned PDF or image, link it to an exam, and ingest into pgvector."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Exam link</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Button
              type="button"
              variant={examMode === "existing" ? "default" : "outline"}
              size="sm"
              onClick={() => setExamMode("existing")}
            >
              Existing exam
            </Button>
            <Button
              type="button"
              variant={examMode === "new" ? "default" : "outline"}
              size="sm"
              onClick={() => setExamMode("new")}
            >
              New exam
            </Button>
          </div>
          {examMode === "existing" ? (
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
          ) : (
            <Input
              placeholder="Exam title (same id as your keys)"
              value={newExamTitle}
              onChange={(e) => setNewExamTitle(e.target.value)}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">File</CardTitle>
        </CardHeader>
        <CardContent>
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border bg-muted/20 px-4 py-10 text-sm text-muted-foreground hover:bg-muted/40">
            <Upload className="h-4 w-4" />
            <span>{file ? file.name : "Drop or click to upload PDF / image"}</span>
            <Input
              type="file"
              accept="application/pdf,image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onPickFile(f);
              }}
            />
          </label>

          {previewUrl && file?.type.startsWith("image/") && (
            <div className="mt-4 overflow-hidden rounded-md border">
              <img src={previewUrl} alt="Preview" className="max-h-72 w-full object-contain bg-muted" />
            </div>
          )}
          {previewUrl && file?.type === "application/pdf" && (
            <div className="mt-4 flex items-center gap-2 rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              <FileScan className="h-4 w-4" />
              PDF ready · {(file.size / 1024).toFixed(0)} KB
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => navigate("/sheets")}>Cancel</Button>
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          {create.isPending ? "Ingesting…" : "Ingest sheet"}
        </Button>
      </div>
    </div>
  );
}