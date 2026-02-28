import { QueryPanel } from "@/components/QueryPanel";

export default function HomePage() {
  return (
    <main>
      <h1>graphRAG</h1>
      <p>Ask a question and inspect the structured answer payload.</p>
      <QueryPanel />
    </main>
  );
}
