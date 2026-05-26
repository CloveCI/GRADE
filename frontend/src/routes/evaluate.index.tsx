import { createFileRoute } from "@tanstack/react-router";
import { EvaluateInner } from "./evaluate-inner";

export const Route = createFileRoute("/evaluate/")({
  component: EvaluatePage,
  validateSearch: (s) => ({ exam: typeof s.exam === "string" ? s.exam : undefined }),
  head: () => ({
    meta: [
      { title: "Evaluate · GRADE" },
      { name: "description", content: "Run server-side OCR + hybrid RAG + Gemini scoring against a selected sheet." },
    ],
  }),
});

function EvaluatePage() {
  const { exam } = Route.useSearch();
  return <EvaluateInner initialExam={exam} />;
}
