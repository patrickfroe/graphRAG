import { Button } from "@/components/ui/button";

export default function ChatPage() {
  return (
    <section className="space-y-4">
      <h2 className="text-2xl font-semibold">Chat</h2>
      <p className="text-muted-foreground">Hauptseite für die Konversation mit deinem graphRAG-System.</p>
      <div className="rounded-lg border p-4">
        <p className="mb-3 text-sm text-muted-foreground">Bereit für den ersten Prompt?</p>
        <Button>Neue Unterhaltung starten</Button>
      </div>
    </section>
  );
}
