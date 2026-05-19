import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KeyRound, FileScan, PlayCircle, ClipboardList, BarChart3, Search, Package } from "lucide-react";
import { Link } from "react-router-dom";

const portals = [
  { title: "Upload bundle", url: "/upload/bundle", icon: Package, desc: "Keys + sheet in one step (recommended for testing).", highlight: true },
  { title: "Keys", url: "/keys", icon: KeyRound, desc: "Upload and manage answer keys per exam." },
  { title: "Sheets", url: "/sheets", icon: FileScan, desc: "Ingest scanned sheets (requires exam_id)." },
  { title: "Evaluate", url: "/evaluate", icon: PlayCircle, desc: "Run server OCR, RAG, and grading." },
  { title: "Results", url: "/results", icon: ClipboardList, desc: "Browse saved evaluations." },
  { title: "Metrics", url: "/metrics", icon: BarChart3, desc: "KPIs and activity." },
  { title: "RAG Explorer", url: "/rag", icon: Search, desc: "Search sheet + key chunks." },
];

const Index = () => {
  return (
    <div className="space-y-8">
      <section>
        <Badge variant="secondary" className="mb-3 uppercase tracking-wider">
          GRADE Portal
        </Badge>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          GRADE Autograder
        </h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Upload answer keys and sheets under the same <strong>exam_id</strong>, index both into pgvector, then
          evaluate with hybrid RAG (model answers + OCR chunks) and optional Gemini grading on the API.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button asChild size="lg">
            <Link to="/upload/bundle">
              <Package className="mr-2 h-4 w-4" />
              Quick test: upload bundle
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to="/evaluate">Evaluate</Link>
          </Button>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {portals.map((p) => (
          <Link key={p.url} to={p.url} className="group">
            <Card
              className={`h-full transition-all hover:-translate-y-0.5 hover:shadow-[var(--shadow-elegant)] ${
                p.highlight ? "border-primary/40 bg-primary/5" : ""
              }`}
            >
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-md transition-colors ${
                      p.highlight
                        ? "bg-primary text-primary-foreground"
                        : "bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground"
                    }`}
                  >
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
