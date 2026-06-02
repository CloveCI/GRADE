import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Database, Sparkles, Layers, ClipboardCheck, CircleCheck, CircleX, Route } from "lucide-react";
import { getDatabaseStatus, getIntegrations, type DatabaseStatus, type IntegrationsStatus } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Props {
  variant?: "full" | "compact";
}

function Pill({ ok, label, icon: Icon }: { ok: boolean; label: string; icon: typeof Database }) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        ok
          ? "border-success/40 bg-success/10 text-success"
          : "border-destructive/40 bg-destructive/10 text-destructive",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      <span>{label}</span>
      {ok ? <CircleCheck className="h-3 w-3" /> : <CircleX className="h-3 w-3" />}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/60 px-4 py-3">
      <div className="kpi-label">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight text-foreground">{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function SystemStatusPanel({ variant = "full" }: Props) {
  const dbQ = useQuery<DatabaseStatus>({
    queryKey: ["database-status"],
    queryFn: getDatabaseStatus,
    refetchInterval: 60_000,
    retry: 0,
  });
  const intQ = useQuery<IntegrationsStatus>({
    queryKey: ["integrations"],
    queryFn: getIntegrations,
    refetchInterval: 60_000,
    retry: 0,
  });

  const apiUnreachable = dbQ.isError && intQ.isError;
  const db = dbQ.data;
  const integ = intQ.data;

  const pills = (
    <div className="flex flex-wrap gap-2">
      <Pill ok={!!db?.connected} icon={Database} label="Postgres" />
      <Pill ok={!!db?.rag_ready && !!db?.pgvector_extension} icon={Layers} label="RAG (pgvector)" />
      <Pill ok={!!db?.evaluation_ready} icon={ClipboardCheck} label="Evaluations" />
      <Pill ok={!!integ?.llm?.ready} icon={Sparkles} label="LLM" />
      <Pill ok={!!integ?.llm_gemini?.ready} icon={Sparkles} label="Gemini" />
      {integ?.llm_openrouter?.api_key_present && (
        <Pill ok={!!integ?.llm_openrouter?.ready} icon={Route} label="OpenRouter" />
      )}
    </div>
  );

  if (apiUnreachable) {
    return (
      <Card className="glass-card border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            API unreachable
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            The GRADE backend at <code className="text-foreground">http://127.0.0.1:8000</code> is not
            responding. Is uvicorn running on port 8000?
          </p>
          <pre className="overflow-x-auto rounded-md border border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
{`docker compose up -d
PYTHONPATH=src uvicorn autograder.api:app --host 127.0.0.1 --port 8000`}
          </pre>
        </CardContent>
      </Card>
    );
  }

  if (variant === "compact") {
    return (
      <Card className="glass-card">
        <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
          {pills}
          {db?.target && (
            <span className="text-xs text-muted-foreground">target: <code>{db.target}</code></span>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="glass-card">
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">System connectivity</CardTitle>
          {db?.target && (
            <span className="text-xs text-muted-foreground">target: <code>{db.target}</code></span>
          )}
        </div>
        {pills}
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Stat
            label="RAG chunks"
            value={db?.counts?.rag_chunks ?? 0}
            sub={`schema ${db?.schema_ready ? "ready" : "pending"}`}
          />
          <Stat
            label="Evaluation results"
            value={db?.counts?.evaluation_results ?? 0}
            sub={`${db?.counts?.answer_keys ?? 0} keys · ${db?.counts?.sheets ?? 0} sheets`}
          />
        </div>
        {!integ?.llm?.ready && (
          <div className="rounded-lg border border-warning/40 bg-warning/5 p-3 text-xs text-warning">
            {integ?.llm_gemini?.api_key_present || integ?.llm_openrouter?.api_key_present ? (
              <>
                LLM not ready
                {integ.llm_gemini?.live_probe?.model ? ` (Gemini: ${integ.llm_gemini.live_probe.model})` : ""}
                {integ.llm_openrouter?.model ? ` (OpenRouter: ${integ.llm_openrouter.model})` : ""}.
                {integ.llm_gemini?.live_probe?.error?.includes("429") ||
                integ.llm_gemini?.live_probe?.error?.includes("quota") ? (
                  <> Gemini rate limited — OpenRouter fallback applies if configured and probed OK. Wait and refresh, or set{" "}
                    <code>GRADE_OPENROUTER_API_KEY</code> from{" "}
                    <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer" className="underline">
                      openrouter.ai
                    </a>
                    .</>
                ) : integ.llm_openrouter?.api_key_present && !integ.llm_openrouter?.ready ? (
                  <> Check OpenRouter key and model <code>{integ.llm_openrouter.model}</code>.</>
                ) : (
                  <> Set <code>GRADE_GEMINI_API_KEY</code> and/or <code>GRADE_OPENROUTER_API_KEY</code>, then restart uvicorn.</>
                )}
              </>
            ) : (
              <>
                Gemini is off. In repo root <code>.env</code> set <code>GRADE_ENABLE_LLM=true</code> and{" "}
                <code>GRADE_GEMINI_API_KEY=…</code>, then restart uvicorn.
              </>
            )}
          </div>
        )}
        {db?.error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
            {db.error}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
