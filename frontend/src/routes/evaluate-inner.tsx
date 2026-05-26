import { useNavigate } from "@tanstack/react-router";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { PlayCircle, AlertTriangle, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import { ProcessTimeline } from "@/components/ProcessTimeline";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  evaluate,
  getDatabaseStatus,
  listExams,
  listSheets,
  type StreamEvent,
} from "@/lib/api";

/** Shared evaluate UI — must not call Route.useSearch() (used from /evaluate/ and /evaluate/$sheetId). */
export function EvaluateInner({
  presetSheetId,
  initialExam,
}: {
  presetSheetId?: string;
  initialExam?: string;
} = {}) {
  const navigate = useNavigate();
  const db = useQuery({ queryKey: ["database-status"], queryFn: getDatabaseStatus, retry: 0 });
  const exams = useQuery({ queryKey: ["exams"], queryFn: listExams, retry: 0 });
  const sheets = useQuery({ queryKey: ["sheets"], queryFn: listSheets, retry: 0 });

  const [examId, setExamId] = useState<string>(initialExam ?? "");
  const [sheetId, setSheetId] = useState<string>(presetSheetId ?? "");

  useEffect(() => {
    if (initialExam) setExamId(initialExam);
  }, [initialExam]);

  useEffect(() => {
    if (presetSheetId) setSheetId(presetSheetId);
  }, [presetSheetId]);

  const [topK, setTopK] = useState(3);
  const [regions, setRegions] = useState(6);
  const [consensus, setConsensus] = useState(true);
  const [demoEvents, setDemoEvents] = useState<StreamEvent[]>([]);
  const [demoRunning, setDemoRunning] = useState(false);

  const filteredSheets = useMemo(
    () => (sheets.data ?? []).filter((s) => !examId || s.exam_id === examId),
    [sheets.data, examId],
  );
  const selectedSheet = (sheets.data ?? []).find((s) => s.sheet_id === sheetId);
  const mismatch = !!(selectedSheet && examId && selectedSheet.exam_id !== examId);
  const missingSheetExam = !!(selectedSheet && !selectedSheet.exam_id?.trim());

  useEffect(() => {
    if (!selectedSheet?.exam_id?.trim()) return;
    if (!examId || examId !== selectedSheet.exam_id) {
      setExamId(selectedSheet.exam_id);
    }
  }, [sheetId, selectedSheet?.exam_id]);

  const ready = !!db.data?.connected && !!db.data?.rag_ready && !!db.data?.evaluation_ready;

  const runM = useMutation({
    mutationFn: () =>
      evaluate({
        sheet_id: sheetId,
        exam_id: examId,
        top_k: topK,
        expected_num_regions: regions,
        use_consensus_ocr: consensus,
      }),
    onSuccess: (r) => {
      toast.success("Evaluation complete");
      navigate({ to: "/results/$id", params: { id: r.result_id } });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const runDemo = async () => {
    setDemoRunning(true);
    setDemoEvents([]);
    const phases: StreamEvent[] = [
      { phase: "started", message: "Bootstrapping evaluation" },
      { phase: "preprocess", message: "Deskew + denoise sheet" },
      { phase: "ocr_region", message: `OCR ${regions} regions (consensus=${consensus})` },
      { phase: "retrieve", message: `Hybrid RAG top_k=${topK}` },
      { phase: "score", message: "Score with rubric + Gemini" },
      { phase: "complete", message: "Done" },
    ];
    for (const ev of phases) {
      await new Promise((r) => setTimeout(r, 600));
      setDemoEvents((prev) => [...prev, ev]);
    }
    setDemoRunning(false);
  };

  return (
    <>
      <PageHeader
        eyebrow="Evaluate"
        title={presetSheetId ? `Run on sheet ${presetSheetId.slice(0, 8)}` : "Run server evaluation"}
        description="Picks the answer key, OCRs the sheet, retrieves hybrid RAG context, then scores with Gemini (or fallback). Result is persisted via insert_evaluation_result."
      />
      <SystemStatusPanel variant="compact" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="glass-card lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <PlayCircle className="h-4 w-4 text-primary" /> Configuration
            </CardTitle>
            <CardDescription>Sheet exam_id must match the selected exam.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Exam</Label>
                <Select value={examId} onValueChange={setExamId}>
                  <SelectTrigger><SelectValue placeholder="Select exam" /></SelectTrigger>
                  <SelectContent>
                    {(exams.data ?? []).map((e) => (
                      <SelectItem key={e.exam_id} value={e.exam_id}>
                        {e.title ? `${e.title} · ${e.exam_id}` : e.exam_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Sheet</Label>
                <Select value={sheetId} onValueChange={setSheetId} disabled={!!presetSheetId}>
                  <SelectTrigger><SelectValue placeholder="Select sheet" /></SelectTrigger>
                  <SelectContent>
                    {filteredSheets.map((s) => (
                      <SelectItem key={s.sheet_id} value={s.sheet_id}>
                        {s.filename ?? s.sheet_id.slice(0, 12)} · {s.exam_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="topk">top_k</Label>
                <Input id="topk" type="number" min={1} max={10} value={topK} onChange={(e) => setTopK(Math.min(10, Math.max(1, Number(e.target.value) || 3)))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="rg">expected_num_regions</Label>
                <Input id="rg" type="number" min={1} max={30} value={regions} onChange={(e) => setRegions(Number(e.target.value) || 6)} />
              </div>
              <div className="flex items-center justify-between rounded-md border border-border/60 bg-card/40 px-3 py-2 md:col-span-2">
                <div>
                  <div className="text-sm font-medium">use_consensus_ocr</div>
                  <div className="text-xs text-muted-foreground">Multi-engine vote per region.</div>
                </div>
                <Switch checked={consensus} onCheckedChange={setConsensus} />
              </div>
            </div>

            {missingSheetExam && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertTriangle className="mt-0.5 h-4 w-4" />
                <span>This sheet has no <code>exam_id</code>. Re-upload it linked to an exam before evaluating.</span>
              </div>
            )}
            {mismatch && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertTriangle className="mt-0.5 h-4 w-4" />
                <span>Sheet exam_id (<code>{selectedSheet?.exam_id}</code>) doesn't match selected exam (<code>{examId}</code>).</span>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              <Button
                size="lg"
                onClick={() => runM.mutate()}
                disabled={!ready || !examId || !sheetId || mismatch || missingSheetExam || runM.isPending}
                className="glow-primary"
              >
                <PlayCircle className="mr-2 h-4 w-4" />
                {runM.isPending ? "Running…" : "Run server evaluation"}
              </Button>
              <Button variant="outline" size="lg" onClick={runDemo} disabled={demoRunning}>
                <Sparkles className="mr-2 h-4 w-4" /> {demoRunning ? "Animating…" : "Demo timeline"}
              </Button>
            </div>
            {runM.isError && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {(runM.error as Error).message}
              </div>
            )}
            {!ready && (
              <div className="text-xs text-muted-foreground">
                Run button is disabled until Postgres + RAG + Evaluation tables are ready (see status pills).
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardHeader>
            <CardTitle className="text-base">Pipeline</CardTitle>
            <CardDescription>{demoEvents.length > 0 ? "Synthetic demo run" : "Phases run server-side"}</CardDescription>
          </CardHeader>
          <CardContent>
            <ProcessTimeline events={demoEvents} active={demoRunning} demo={demoEvents.length > 0} />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
