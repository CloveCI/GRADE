import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { uploadKeyFile, uploadKeyJson, slugifyExamId, type AnswerKey } from "@/lib/api";

export const Route = createFileRoute("/keys/new")({
  component: NewKey,
  head: () => ({
    meta: [
      { title: "New answer key · GRADE" },
      { name: "description", content: "Upload a JSON or PDF answer key, or compose one by hand." },
    ],
  }),
});

function NewKey() {
  const navigate = useNavigate();

  // file upload state
  const [examIdFile, setExamIdFile] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [defaultMax, setDefaultMax] = useState<number>(10);

  // manual state
  const [examIdManual, setExamIdManual] = useState("");
  const [title, setTitle] = useState("");
  const [json, setJson] = useState(
    `[\n  {\n    "question_id": "q1",\n    "question_text": "Define photosynthesis.",\n    "expected_answer": "Process by which plants convert light energy into chemical energy.",\n    "max_marks": 5\n  }\n]`,
  );

  const fileM = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Pick a file first.");
      const id = examIdFile.trim() || slugifyExamId(file.name.replace(/\.[^.]+$/, ""));
      return uploadKeyFile({ file, exam_id: id, default_max_marks: defaultMax });
    },
    onSuccess: (data) => {
      toast.success(`Key uploaded — ${data.questions} questions`);
      navigate({ to: "/keys/$examId", params: { examId: data.exam_id } });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const jsonM = useMutation({
    mutationFn: () => {
      const id = examIdManual.trim() || slugifyExamId(title);
      let questions: AnswerKey["questions"];
      try {
        questions = JSON.parse(json);
      } catch {
        throw new Error("Questions JSON is invalid.");
      }
      if (!Array.isArray(questions)) throw new Error("Questions must be an array.");
      const normalized = questions.map((q, i) => {
        const row = q as Record<string, unknown>;
        const expected =
          String(row.expected_answer ?? row.question_text ?? "").trim();
        if (!expected) {
          throw new Error(`Question ${i + 1} needs expected_answer (or question_text).`);
        }
        const max = Number(row.max_marks ?? 0);
        if (!Number.isFinite(max) || max <= 0) {
          throw new Error(`Question ${i + 1} max_marks must be greater than 0.`);
        }
        return {
          question_id: String(row.question_id ?? `Q${i + 1}`),
          expected_answer: expected,
          max_marks: max,
          domain: typeof row.domain === "string" ? row.domain : undefined,
        };
      });
      return uploadKeyJson({ exam_id: id, questions: normalized });
    },
    onSuccess: (data) => {
      toast.success("Answer key saved");
      navigate({ to: "/keys/$examId", params: { examId: data.exam_id } });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <>
      <PageHeader
        eyebrow="Answer keys"
        title="Create answer key"
        description="Upload a JSON / PDF key file, or compose questions inline. PDFs are parsed server-side."
      />
      <Tabs defaultValue="file">
        <TabsList>
          <TabsTrigger value="file">Upload file</TabsTrigger>
          <TabsTrigger value="manual">Compose JSON</TabsTrigger>
        </TabsList>
        <TabsContent value="file">
          <Card className="glass-card">
            <CardHeader>
              <CardTitle className="text-base">From JSON or PDF</CardTitle>
              <CardDescription>PDF goes through server-side OCR + extraction.</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  fileM.mutate();
                }}
              >
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="space-y-1.5 md:col-span-1">
                    <Label htmlFor="examIdF">Exam id</Label>
                    <Input id="examIdF" value={examIdFile} onChange={(e) => setExamIdFile(e.target.value)} placeholder="biology-midterm" />
                  </div>
                  <div className="space-y-1.5 md:col-span-1">
                    <Label htmlFor="dmm">Default max marks</Label>
                    <Input id="dmm" type="number" min={1} value={defaultMax} onChange={(e) => setDefaultMax(Number(e.target.value) || 10)} />
                  </div>
                  <div className="space-y-1.5 md:col-span-1">
                    <Label htmlFor="kf">Key file</Label>
                    <Input id="kf" type="file" accept=".json,.pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                  </div>
                </div>
                <Button type="submit" disabled={fileM.isPending || !file}>
                  {fileM.isPending ? "Uploading…" : "Upload key file"}
                </Button>
                {fileM.isError && (
                  <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                    {(fileM.error as Error).message}
                  </div>
                )}
              </form>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="manual">
          <Card className="glass-card">
            <CardHeader>
              <CardTitle className="text-base">Compose JSON</CardTitle>
              <CardDescription>Edit the array of questions then save.</CardDescription>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  jsonM.mutate();
                }}
              >
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="title">Title</Label>
                    <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="examIdM">Exam id</Label>
                    <Input id="examIdM" value={examIdManual} onChange={(e) => setExamIdManual(e.target.value)} placeholder={slugifyExamId(title)} />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="questions">Questions JSON</Label>
                  <Textarea id="questions" value={json} onChange={(e) => setJson(e.target.value)} className="min-h-[260px] font-mono text-xs" />
                </div>
                <Button type="submit" disabled={jsonM.isPending}>
                  {jsonM.isPending ? "Saving…" : "Save key"}
                </Button>
                {jsonM.isError && (
                  <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                    {(jsonM.error as Error).message}
                  </div>
                )}
              </form>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  );
}
