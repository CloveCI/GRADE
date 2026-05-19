import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { ProcessTimeline } from "@/components/ProcessTimeline";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";

export default function Evaluate() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { sheetId: routeSheetId } = useParams();
  const [search] = useSearchParams();
  const initialSheet = routeSheetId || search.get("sheet") || search.get("sheet_id") || "";
  const initialExam = search.get("exam") || search.get("exam_id") || "";
  const [sheetId, setSheetId] = useState(initialSheet);
  const [examId, setExamId] = useState(initialExam);
  const [demoTimeline, setDemoTimeline] = useState(false);
  const [useConsensusOcr, setUseConsensusOcr] = useState(false);
  const [expectedRegions, setExpectedRegions] = useState("");

  const { data: exams } = useQuery({ queryKey: ["exams"], queryFn: api.listExams });
  const { data: sheets } = useQuery({ queryKey: ["sheets"], queryFn: () => api.listSheets() });

  useEffect(() => {
    if (routeSheetId) setSheetId(routeSheetId);
    const ex = search.get("exam") || search.get("exam_id");
    if (ex) setExamId(ex);
  }, [routeSheetId, search]);

  const sheetsForExam = useMemo(() => {
    if (!examId) return sheets ?? [];
    return (sheets ?? []).filter((s) => s.examId === examId);
  }, [sheets, examId]);

  const selectedSheet = useMemo(
    () => (sheets ?? []).find((s) => s.id === sheetId),
    [sheets, sheetId],
  );

  useEffect(() => {
    if (selectedSheet?.examId && !examId) {
      setExamId(selectedSheet.examId);
    }
  }, [selectedSheet, examId]);

  const examMismatch =
    Boolean(selectedSheet?.examId && examId && selectedSheet.examId !== examId);

  const canRun = useMemo(
    () => sheetId.trim() && examId.trim() && !examMismatch,
    [sheetId, examId, examMismatch],
  );

  const { data: integrations } = useQuery({
    queryKey: ["integrations"],
    queryFn: () => api.integrations(),
    staleTime: 60_000,
  });
  const llm = integrations?.llm_gemini;
  const geminiReady = Boolean(llm?.ready);

  const evaluateMutation = useMutation({
    mutationFn: () =>
      api.evaluate({
        sheetId: sheetId.trim(),
        examId: examId.trim(),
        useConsensusOcr,
        expectedNumRegions: expectedRegions.trim() === "" ? null : Number(expectedRegions),
      }),
    onSuccess: (r) => {
      queryClient.invalidateQueries({ queryKey: ["results"] });
      queryClient.invalidateQueries({ queryKey: ["result", r.id] });
      setDemoTimeline(false);
      navigate(`/results/${encodeURIComponent(r.id)}`);
      toast.success("Evaluation complete — opening result");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evaluate"
        description="Run OCR, match keys, hybrid RAG (sheet + keys), and score via the API. Pick an ingested sheet linked to the same exam as your keys."
      />

      {llm && !geminiReady ? (
        <Alert>
          <AlertTitle>Gemini not fully enabled on the API</AlertTitle>
          <AlertDescription className="text-sm">
            Set <code className="rounded bg-muted px-1">GRADE_ENABLE_LLM=true</code> and{" "}
            <code className="rounded bg-muted px-1">GRADE_GEMINI_API_KEY</code> in the repository root{" "}
            <code className="rounded bg-muted px-1">.env</code>, then restart uvicorn. Fallback scoring still runs.
          </AlertDescription>
        </Alert>
      ) : null}

      {geminiReady ? (
        <Alert className="border-[hsl(var(--success))]/40 bg-[hsl(var(--success))]/5">
          <AlertTitle>Gemini ready</AlertTitle>
          <AlertDescription className="text-sm">
            Server reports LLM + API key present. Grading uses your configured Gemini model.
          </AlertDescription>
        </Alert>
      ) : null}

      {examMismatch ? (
        <Alert variant="destructive">
          <AlertTitle>Exam mismatch</AlertTitle>
          <AlertDescription>
            Sheet is linked to <strong>{selectedSheet?.examId}</strong> but you selected exam{" "}
            <strong>{examId}</strong>. They must match.
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run settings</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Exam</Label>
            <Select value={examId} onValueChange={setExamId}>
              <SelectTrigger>
                <SelectValue placeholder="Select exam" />
              </SelectTrigger>
              <SelectContent>
                {exams?.map((e) => (
                  <SelectItem key={e.id} value={e.id}>
                    {e.title} ({e.id})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Sheet</Label>
            <Select value={sheetId} onValueChange={setSheetId}>
              <SelectTrigger>
                <SelectValue placeholder="Select sheet" />
              </SelectTrigger>
              <SelectContent>
                {(examId ? sheetsForExam : sheets)?.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.filename} {s.examId ? `· ${s.examId}` : "· no exam"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="sheet_id">Sheet ID (advanced)</Label>
            <Input
              id="sheet_id"
              value={sheetId}
              onChange={(e) => setSheetId(e.target.value)}
              placeholder="sheet_uuid"
            />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="exam_id">Exam ID (advanced)</Label>
            <Input
              id="exam_id"
              value={examId}
              onChange={(e) => setExamId(e.target.value)}
              placeholder="exam_id"
            />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="expected_regions">Expected answer regions (optional)</Label>
            <Input
              id="expected_regions"
              value={expectedRegions}
              onChange={(e) => setExpectedRegions(e.target.value)}
              placeholder="Leave blank for auto"
              inputMode="numeric"
            />
          </div>
          <div className="flex items-center space-x-2 sm:col-span-2">
            <Checkbox
              id="consensus_ocr"
              checked={useConsensusOcr}
              onCheckedChange={(v) => setUseConsensusOcr(v === true)}
            />
            <Label htmlFor="consensus_ocr" className="text-sm font-normal leading-none">
              Use consensus OCR (multiple engines)
            </Label>
          </div>
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <Button
              onClick={() => evaluateMutation.mutate()}
              disabled={!canRun || evaluateMutation.isPending}
            >
              {evaluateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              ) : null}
              Run server evaluation
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!canRun || evaluateMutation.isPending}
              onClick={() => {
                setDemoTimeline(true);
                toast.message("Demo timeline", {
                  description: "Synthetic UI only — use Run server evaluation for real grading.",
                });
              }}
            >
              Demo timeline only
            </Button>
          </div>
        </CardContent>
      </Card>

      {demoTimeline && canRun ? (
        <ProcessTimeline
          key={`${sheetId}-${examId}`}
          sheetId={sheetId.trim()}
          examId={examId.trim()}
          onComplete={(r) =>
            navigate(`/results/${encodeURIComponent(r.id)}`, {
              state: { evaluationResult: r },
            })
          }
        />
      ) : (
        <Card>
          <CardContent className="py-8 text-sm text-muted-foreground">
            Upload keys and a sheet with the same <strong>exam_id</strong> (try{" "}
            <Link to="/upload/bundle" className="text-primary underline">
              Upload bundle
            </Link>
            ), then run server evaluation. RAG pulls chunks from both <code>keys_&#123;exam&#125;</code> and{" "}
            <code>sheet_&#123;id&#125;</code>.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
