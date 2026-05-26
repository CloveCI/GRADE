import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Package, Upload } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { uploadExamBundle, slugifyExamId } from "@/lib/api";

/** Warn when filenames suggest key vs sheet were picked in the wrong inputs. */
function bundleFileHint(key: File | null, sheet: File | null): string | null {
  if (!key || !sheet) return null;
  const kn = key.name.toLowerCase();
  const sn = sheet.name.toLowerCase();
  const scanInKey = /docscanner|scan|whatsapp|camera|img_|photo/i.test(kn);
  const keyInSheet = /\bkey\b/.test(sn) && !/docscanner|scan/i.test(sn);
  if (scanInKey && keyInSheet) {
    return "These filenames look swapped: put Key.pdf (or a .json key) in Answer key, and the DocScanner student scan in Student sheet.";
  }
  if (scanInKey) {
    return "DocScanner-style PDFs are usually student sheets. Answer keys should be text-based PDFs (e.g. Key.pdf) or JSON — unless you intentionally OCR a scanned key.";
  }
  return null;
}

export const Route = createFileRoute("/upload/bundle")({
  component: UploadBundle,
  head: () => ({
    meta: [
      { title: "Upload bundle · GRADE" },
      { name: "description", content: "Upload exam id + answer key + scanned sheet in a single bundle and jump straight to evaluation." },
    ],
  }),
});

function UploadBundle() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [examId, setExamId] = useState("");
  const [keyFile, setKeyFile] = useState<File | null>(null);
  const [sheetFile, setSheetFile] = useState<File | null>(null);
  const fileHint = bundleFileHint(keyFile, sheetFile);

  const m = useMutation({
    mutationFn: () => {
      const id = examId.trim() || slugifyExamId(title);
      if (!keyFile || !sheetFile) throw new Error("Both key file and sheet file are required.");
      return uploadExamBundle({ exam_id: id, key_file: keyFile, sheet_file: sheetFile });
    },
    onSuccess: (data) => {
      toast.success(`Bundle uploaded — exam ${data.exam_id}`);
      navigate({ to: "/evaluate/$sheetId", params: { sheetId: data.sheet_id }, search: { exam: data.exam_id } as any });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <>
      <PageHeader
        eyebrow="Quick test"
        title="Upload exam bundle"
        description="Combine the exam id, an answer key file, and a scanned sheet. The server provisions the exam row, ingests RAG, and prepares evaluation in one step."
      />
      <SystemStatusPanel variant="compact" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="glass-card lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Package className="h-4 w-4 text-primary" /> Bundle
            </CardTitle>
            <CardDescription>
              <strong>Answer key</strong> = text PDF (e.g. <code>Key.pdf</code>) or <code>.json</code>.
              <strong> Student sheet</strong> = scan/image (e.g. <code>DocScanner … am.pdf</code>).
              Both share the same <code>exam_id</code>.
            </CardDescription>
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
                  <Label htmlFor="title">Exam title</Label>
                  <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Biology midterm 2026" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="examId">Exam id (optional)</Label>
                  <Input id="examId" value={examId} onChange={(e) => setExamId(e.target.value)} placeholder={slugifyExamId(title) || "biology-midterm-2026"} />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="key">Answer key — text PDF or JSON</Label>
                  <Input id="key" type="file" accept=".json,.pdf" onChange={(e) => setKeyFile(e.target.files?.[0] ?? null)} />
                  {keyFile && (
                    <p className="text-xs text-muted-foreground truncate" title={keyFile.name}>
                      Selected: {keyFile.name}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="sheet">Student sheet — scan (PDF or image)</Label>
                  <Input id="sheet" type="file" accept=".pdf,.png,.jpg,.jpeg,.tiff" onChange={(e) => setSheetFile(e.target.files?.[0] ?? null)} />
                  {sheetFile && (
                    <p className="text-xs text-muted-foreground truncate" title={sheetFile.name}>
                      Selected: {sheetFile.name}
                    </p>
                  )}
                </div>
              </div>
              {fileHint && (
                <div className="rounded-md border border-warning/40 bg-warning/5 p-3 text-sm text-warning">
                  {fileHint}
                </div>
              )}
              <Button type="submit" size="lg" disabled={m.isPending || !keyFile || !sheetFile}>
                <Upload className="mr-2 h-4 w-4" />
                {m.isPending ? "Uploading…" : "Upload bundle"}
              </Button>
              {m.isError && (
                <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                  {(m.error as Error).message}
                </div>
              )}
            </form>
          </CardContent>
        </Card>
        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="text-base">What happens next</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <p>1. Server stores key + sheet rows under <code>exam_id</code>.</p>
            <p>2. RAG corpora <code>keys_{`{exam_id}`}</code> + <code>sheet_{`{sheet_id}`}</code> are indexed in pgvector.</p>
            <p>3. You're redirected to the evaluator with the sheet preselected.</p>
            <p className="rounded-md border border-warning/40 bg-warning/5 p-2 text-xs text-warning">
              Returns 503 if Postgres or RAG/eval tables aren't ready — check the status panel above.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
