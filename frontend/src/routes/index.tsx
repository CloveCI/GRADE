import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Package,
  KeyRound,
  FileScan,
  PlayCircle,
  ClipboardCheck,
  Database,
  ArrowRight,
  GraduationCap,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { getMetricsOverview } from "@/lib/api";

export const Route = createFileRoute("/")({
  component: Dashboard,
  head: () => ({
    meta: [
      { title: "Dashboard · GRADE" },
      { name: "description", content: "GRADE Autograder dashboard — connectivity, portals, and quick-test bundle upload." },
    ],
  }),
});

const PORTALS = [
  { to: "/upload/bundle", title: "Upload bundle", desc: "Exam + key + sheet in one shot — fastest test path.", icon: Package, accent: true },
  { to: "/keys", title: "Answer keys", desc: "Manage exam keys (JSON, PDF, or manual).", icon: KeyRound },
  { to: "/sheets", title: "Sheets", desc: "Scanned student response sheets.", icon: FileScan },
  { to: "/evaluate", title: "Evaluate", desc: "OCR + hybrid RAG + Gemini scoring.", icon: PlayCircle },
  { to: "/results", title: "Results", desc: "Per-question rubric bars and PDF reports.", icon: ClipboardCheck },
  { to: "/rag", title: "RAG Explorer", desc: "Inspect chunks across keys + sheet corpora.", icon: Database },
];

function Dashboard() {
  const m = useQuery({ queryKey: ["metrics"], queryFn: getMetricsOverview, retry: 0 });

  return (
    <>
      <section className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/40 p-8">
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: "var(--gradient-cyber)" }}
        />
        <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-primary">
              <GraduationCap className="h-3.5 w-3.5" /> Graduate Response Assessment & Document Evaluation
            </div>
            <h1 className="max-w-2xl text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
              Autograde scanned exams with OCR, hybrid RAG, and Gemini.
            </h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Keys and sheets persist in PostgreSQL + pgvector. RAG and grading run server-side on
              FastAPI — the browser never touches API keys or the database.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild size="lg" className="glow-primary">
              <Link to="/upload/bundle">
                <Package className="mr-2 h-4 w-4" /> Quick test: upload bundle
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/evaluate">Open evaluator</Link>
            </Button>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard label="Exams" value={m.data?.total_exams ?? "—"} icon={<KeyRound className="h-5 w-5" />} />
        <KpiCard label="Sheets" value={m.data?.total_sheets ?? "—"} icon={<FileScan className="h-5 w-5" />} />
        <KpiCard label="Results" value={m.data?.total_results ?? "—"} icon={<ClipboardCheck className="h-5 w-5" />} />
        <KpiCard label="RAG chunks" value={m.data?.rag_chunks ?? "—"} icon={<Database className="h-5 w-5" />} />
      </div>

      <SystemStatusPanel />

      <section className="space-y-3">
        <PageHeader eyebrow="Portals" title="Where do you want to go?" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PORTALS.map((p) => (
            <Link key={p.to} to={p.to} className="group">
              <Card className={`glass-card card-hover h-full ${p.accent ? "border-primary/40" : ""}`}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <p.icon className="h-4 w-4 text-primary" /> {p.title}
                  </CardTitle>
                  <CardDescription>{p.desc}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="inline-flex items-center text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                    Open <ArrowRight className="ml-1 h-3 w-3" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
