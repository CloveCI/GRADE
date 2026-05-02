import { PagePlaceholder } from "@/components/PagePlaceholder";

export default function RagExplorer() {
  return (
    <PagePlaceholder
      title="RAG Explorer"
      description="Search rag_chunks across exams or scoped to a single sheet. Reused as a side panel."
      phase="Phase 10"
      bullets={[
        "Query input with optional exam/sheet scope",
        "POST /rag/search → ranked chunk previews",
        "Embedded panel inside /sheets/:id and /results/:id",
      ]}
    />
  );
}