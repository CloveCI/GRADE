import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { KeyRound, FileScan, ClipboardCheck, Database, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import { getMetricsOverview } from "@/lib/api";

export const Route = createFileRoute("/metrics")({
  component: MetricsPage,
  head: () => ({
    meta: [
      { title: "Metrics · GRADE" },
      { name: "description", content: "Operational KPIs and connectivity status for the GRADE backend." },
    ],
  }),
});

function MetricsPage() {
  const q = useQuery({ queryKey: ["metrics"], queryFn: getMetricsOverview, retry: 0 });
  const m = q.data;
  return (
    <>
      <PageHeader eyebrow="Operations" title="Metrics" description="High-level signal from the FastAPI backend." />
      <SystemStatusPanel variant="compact" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
        <KpiCard label="Exams" value={m?.total_exams ?? "—"} icon={<KeyRound className="h-5 w-5" />} />
        <KpiCard label="Keys" value={m?.total_keys ?? "—"} icon={<Sparkles className="h-5 w-5" />} />
        <KpiCard label="Sheets" value={m?.total_sheets ?? "—"} icon={<FileScan className="h-5 w-5" />} />
        <KpiCard label="Results" value={m?.total_results ?? "—"} icon={<ClipboardCheck className="h-5 w-5" />} />
        <KpiCard label="RAG chunks" value={m?.rag_chunks ?? "—"} icon={<Database className="h-5 w-5" />} />
      </div>
      {m?.avg_score != null && (
        <KpiCard
          label="Average awarded %"
          value={`${Math.round(m.avg_score * 100)}%`}
          hint="across persisted evaluation results"
        />
      )}
    </>
  );
}
