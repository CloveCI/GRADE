import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { EvaluateInner } from "./evaluate-inner";
import { listSheets } from "@/lib/api";

export const Route = createFileRoute("/evaluate/$sheetId")({
  validateSearch: (s) => ({ exam: typeof s.exam === "string" ? s.exam : undefined }),
  component: EvaluateForSheet,
  head: ({ params }) => ({
    meta: [
      { title: `Evaluate sheet ${params.sheetId.slice(0, 8)} · GRADE` },
      { name: "description", content: "Server-side OCR + hybrid RAG + Gemini scoring for a preselected sheet." },
    ],
  }),
});

function EvaluateForSheet() {
  const { sheetId } = Route.useParams();
  const { exam } = Route.useSearch();
  // Warm the sheets cache so EvaluateInner can render filename labels.
  useQuery({ queryKey: ["sheets"], queryFn: listSheets, retry: 0 });
  return <EvaluateInner presetSheetId={sheetId} initialExam={exam} />;
}
