import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KeyRound, FileScan, PlayCircle, ClipboardList, BarChart3, Search } from "lucide-react";
import { Link } from "react-router-dom";

const portals = [
  { title: "Keys", url: "/keys", icon: KeyRound, desc: "Upload and manage answer keys per exam." },
  { title: "Sheets", url: "/sheets", icon: FileScan, desc: "Ingest scanned sheets into pgvector." },
  { title: "Evaluate", url: "/evaluate", icon: PlayCircle, desc: "Run live grading with SSE timeline." },
  { title: "Results", url: "/results", icon: ClipboardList, desc: "Browse saved evaluations." },
  { title: "Metrics", url: "/metrics", icon: BarChart3, desc: "KPIs, charts, and recent activity." },
  { title: "RAG Explorer", url: "/rag", icon: Search, desc: "Query chunks across exams and sheets." },
];

const Index = () => {
  return (
    <div className="space-y-8">
      <section>
        <Badge variant="secondary" className="mb-3 uppercase tracking-wider">
          Phase 0 · Shell ready
        </Badge>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          GRADE Autograder
        </h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Four linked portals — Keys, Sheets, Evaluate, and Results — backed by pgvector retrieval and a
          live SSE process timeline. The shell is in place; portals will land in the next phases.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {portals.map((p) => (
          <Link key={p.url} to={p.url} className="group">
            <Card className="h-full transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-elegant)]">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                    <p.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="text-lg">{p.title}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <CardDescription>{p.desc}</CardDescription>
              </CardContent>
            </Card>
          </Link>
        ))}
      </section>
    </div>
  );
};

export default Index;
