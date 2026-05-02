import { useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
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

  const canRun = useMemo(() => sheetId.trim() && examId.trim(), [sheetId, examId]);

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
    onError: (e: Error) => {
      toast.error(e.message);
    },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evaluate"
        description="Run the real pipeline on the uploaded sheet and exam keys (OCR → scoring). Gemini runs on the API server when enabled there."
      />

      {llm && !geminiReady ? (
        <Alert>
          <AlertTitle>Gemini not fully enabled on the API</AlertTitle>
          <AlertDescription className="text-sm">
            Set <code className="rounded bg-muted px-1">GRADE_ENABLE_LLM=true</code> and{" "}
            <code className="rounded bg-muted px-1">GRADE_GEMINI_API_KEY</code> (or{" "}
            <code className="rounded bg-muted px-1">GEMINI_API_KEY</code>) in the{" "}
            <strong>repository root</strong> <code className="rounded bg-muted px-1">.env</code>, install{" "}
            <code className="rounded bg-muted px-1">google-generativeai</code>, then restart uvicorn. Evaluation still
            runs using the server fallback scorer if LLM is off.
          </AlertDescription>
        </Alert>
      ) : null}

      {geminiReady ? (
        <Alert className="border-[hsl(var(--success))]/40 bg-[hsl(var(--success))]/5">
          <AlertTitle>Gemini ready</AlertTitle>
          <AlertDescription className="text-sm">
            The API reports LLM + key present. Grading uses your configured model (default{" "}
            <code className="rounded bg-muted px-1">gemini-2.0-flash</code> via{" "}
            <code className="rounded bg-muted px-1">GRADE_LLM_MODEL</code> on the server).
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run settings</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="sheet_id">Sheet ID</Label>
            <Input
              id="sheet_id"
              value={sheetId}
              onChange={(e) => setSheetId(e.target.value)}
              placeholder="sheet_uuid"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="exam_id">Exam ID</Label>
            <Input id="exam_id" value={examId} onChange={(e) => setExamId(e.target.value)} placeholder="exam_id" />
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
            <p className="text-xs text-muted-foreground">Passed to preprocess as hint when set.</p>
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
                toast.message("Demo timeline", { description: "Synthetic UI only — use Run server evaluation for real OCR and Gemini." });
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
            Enter sheet and exam IDs from your ingested data, then <strong>Run server evaluation</strong>. The API
            loads the stored PDF, runs OCR, matches keys from Postgres, scores with Gemini when enabled, and saves the
            result for this results page and PDF export.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
