import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, BarChart3, ClipboardList, FileScan, KeyRound } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { Card, CardContent } from "@/components/ui/card";

export default function Metrics() {
  const { data, isLoading } = useQuery({
    queryKey: ["metrics-overview"],
    queryFn: api.metricsOverview,
  });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading metrics…</p>;
  }

  if (!data) {
    return <p className="text-sm text-destructive">Could not load metrics.</p>;
  }

  const avgPct = `${Math.round((data.avgTotalPct || 0) * 100)}%`;
  const lowPct = `${Math.round((data.lowConfidenceRate || 0) * 100)}%`;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Metrics dashboard"
        description="Quick reference KPIs from live PostgreSQL evaluation data."
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <KpiCard label="Sheets" value={data.sheets} hint="Uploaded answer sheets" icon={FileScan} />
        <KpiCard label="Keys" value={data.keys} hint="Stored answer key rows" icon={KeyRound} />
        <KpiCard label="Evaluations" value={data.results} hint="Saved grading runs" icon={ClipboardList} />
        <KpiCard label="Exams" value={data.exams} hint="Distinct exam IDs" icon={BarChart3} />
        <KpiCard label="Avg score" value={avgPct} hint="Mean total_marks/max_total" icon={Activity} tone="success" />
        <KpiCard
          label="Low confidence"
          value={lowPct}
          hint={`Last 24h evaluations: ${data.last24h}`}
          icon={AlertTriangle}
          tone={data.lowConfidenceRate > 0.25 ? "warning" : "default"}
        />
      </div>
      <Card>
        <CardContent className="py-5 text-sm text-muted-foreground">
          Charts (distribution / confidence trend / top exams) can now be added on top of this live metrics endpoint.
        </CardContent>
      </Card>
    </div>
  );
}