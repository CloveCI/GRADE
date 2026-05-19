import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Trash2, Plus, Upload } from "lucide-react";

interface KeyDraft {
  questionId: string;
  prompt: string;
  answer: string;
  maxMarks: number;
}

const blank = (i: number): KeyDraft => ({
  questionId: `Q${i + 1}`,
  prompt: "",
  answer: "",
  maxMarks: 4,
});

function parseKeyJson(text: string): KeyDraft[] {
  const parsed = JSON.parse(text) as Record<string, unknown>;
  const arr = Array.isArray(parsed)
    ? parsed
    : (parsed.questions as unknown[]) ?? [];
  return (arr as Record<string, unknown>[]).map((row, i) => ({
    questionId: String(row.question_id ?? row.questionId ?? row.id ?? `Q${i + 1}`),
    prompt: String(row.prompt ?? row.question ?? row.question_id ?? row.questionId ?? ""),
    answer: String(row.expected_answer ?? row.answer ?? row.expected ?? ""),
    maxMarks: Number(row.max_marks ?? row.maxMarks ?? row.max ?? 4),
  }));
}

export default function KeyNew() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: exams } = useQuery({ queryKey: ["exams"], queryFn: api.listExams });

  const [examMode, setExamMode] = useState<"existing" | "new">("existing");
  const [examId, setExamId] = useState<string>("");
  const [newExamTitle, setNewExamTitle] = useState("");
  const [drafts, setDrafts] = useState<KeyDraft[]>([blank(0)]);
  const [keyFile, setKeyFile] = useState<File | null>(null);
  const [defaultMaxMarks, setDefaultMaxMarks] = useState(4);

  const handleJson = async (file: File) => {
    try {
      const text = await file.text();
      const next = parseKeyJson(text);
      if (next.length === 0) throw new Error("Empty key file");
      setDrafts(next);
      setKeyFile(file);
      toast.success(`Parsed ${next.length} questions — will upload to server on save`);
    } catch {
      toast.error(
        "Could not parse JSON. Use { exam_id, questions: [{ question_id, expected_answer, max_marks }] }.",
      );
    }
  };

  const onUpload = (file: File) => {
    setKeyFile(file);
    if (file.type === "application/json" || file.name.endsWith(".json")) {
      void handleJson(file);
    } else {
      toast.message(`PDF selected: ${file.name}`, {
        description: "Saved on server when you click Save keys (requires exam_id).",
      });
    }
  };

  const create = useMutation({
    mutationFn: async () => {
      let targetExamId = examId;
      if (examMode === "new") {
        if (!newExamTitle.trim()) throw new Error("Enter an exam title");
        const exam = await api.createExam(newExamTitle.trim());
        targetExamId = exam.id;
      }
      if (!targetExamId) throw new Error("Pick an exam");

      if (keyFile) {
        await api.uploadKeyFile(targetExamId, keyFile, defaultMaxMarks);
        return targetExamId;
      }

      const valid = drafts.filter((d) => d.answer.trim());
      if (valid.length === 0) throw new Error("Add at least one question with an expected answer");
      await api.createKeys(
        targetExamId,
        valid.map((d) => ({
          questionId: d.questionId,
          prompt: d.prompt || d.questionId,
          answer: d.answer,
          maxMarks: d.maxMarks,
        })),
      );
      return targetExamId;
    },
    onSuccess: (targetExamId) => {
      qc.invalidateQueries({ queryKey: ["exams"] });
      qc.invalidateQueries({ queryKey: ["exams-with-counts"] });
      qc.invalidateQueries({ queryKey: ["exam", targetExamId] });
      toast.success("Keys saved and indexed for RAG");
      navigate(`/keys/${targetExamId}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="New keys"
        description="Upload JSON/PDF to the API (indexed as keys_{exam_id}) or enter questions manually."
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Exam</CardTitle>
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
                <SelectValue placeholder="Pick an exam" />
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
              placeholder="Exam title (e.g. Physics 101 — Final)"
              value={newExamTitle}
              onChange={(e) => setNewExamTitle(e.target.value)}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base">Upload key file</CardTitle>
          <Badge variant="outline">JSON or PDF → API</Badge>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-border bg-muted/20 px-4 py-8 text-sm text-muted-foreground hover:bg-muted/40">
            <Upload className="h-4 w-4" />
            <span>{keyFile ? keyFile.name : "Drop or click to upload"}</span>
            <input
              type="file"
              accept=".json,application/json,application/pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUpload(f);
              }}
            />
          </label>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">PDF default marks</span>
            <Input
              type="number"
              min={1}
              className="w-24"
              value={defaultMaxMarks}
              onChange={(e) => setDefaultMaxMarks(Number(e.target.value) || 4)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle className="text-base">Questions ({drafts.length})</CardTitle>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setDrafts((d) => [...d, blank(d.length)])}
            disabled={Boolean(keyFile?.name.endsWith(".pdf"))}
          >
            <Plus className="mr-1 h-4 w-4" /> Add question
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {keyFile?.name.endsWith(".pdf") ? (
            <p className="text-sm text-muted-foreground">
              PDF keys are parsed on the server. Clear the file above to edit questions manually.
            </p>
          ) : (
            drafts.map((d, i) => (
              <div
                key={i}
                className="grid gap-2 rounded-md border bg-card p-3 sm:grid-cols-[80px_1fr_80px_auto]"
              >
                <Input
                  value={d.questionId}
                  onChange={(e) =>
                    setDrafts((arr) =>
                      arr.map((x, j) => (j === i ? { ...x, questionId: e.target.value } : x)),
                    )
                  }
                  aria-label="Question ID"
                />
                <div className="space-y-2">
                  <Input
                    placeholder="Prompt (optional)"
                    value={d.prompt}
                    onChange={(e) =>
                      setDrafts((arr) =>
                        arr.map((x, j) => (j === i ? { ...x, prompt: e.target.value } : x)),
                      )
                    }
                  />
                  <Textarea
                    placeholder="Expected answer"
                    value={d.answer}
                    rows={2}
                    onChange={(e) =>
                      setDrafts((arr) =>
                        arr.map((x, j) => (j === i ? { ...x, answer: e.target.value } : x)),
                      )
                    }
                  />
                </div>
                <Input
                  type="number"
                  min={1}
                  value={d.maxMarks}
                  onChange={(e) =>
                    setDrafts((arr) =>
                      arr.map((x, j) =>
                        j === i ? { ...x, maxMarks: Number(e.target.value) } : x,
                      ),
                    )
                  }
                  aria-label="Max marks"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => setDrafts((arr) => arr.filter((_, j) => j !== i))}
                  disabled={drafts.length === 1}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => navigate("/keys")}>
          Cancel
        </Button>
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          {create.isPending ? "Saving…" : "Save keys"}
        </Button>
      </div>
    </div>
  );
}
