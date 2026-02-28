'use client';

import { FormEvent, useMemo, useState } from 'react';

type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

type Source = {
  id: string;
  title: string;
};

type Entity = {
  id: string;
  label: string;
};

type GraphPreview = {
  nodes: number;
  edges: number;
};

type TraceStep = {
  step: string;
  detail: string;
};

type ChatResponse = {
  answer: string;
  sources: Source[];
  entities: Entity[];
  graphPreview: GraphPreview | null;
  trace: TraceStep[];
};

const api = {
  async chat(query: string): Promise<ChatResponse> {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });

    if (!res.ok) {
      throw new Error('Chat request failed.');
    }

    return res.json();
  },
};

function RightPanel({ response }: { response: ChatResponse | null }) {
  if (!response) {
    return <aside className="rounded border p-4 text-sm text-zinc-500">Noch keine Antwort.</aside>;
  }

  return (
    <aside className="space-y-4 rounded border p-4 text-sm">
      <section>
        <h3 className="font-semibold">Sources</h3>
        <ul className="mt-2 list-disc pl-5">
          {response.sources.map((source) => (
            <li key={source.id}>{source.title}</li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="font-semibold">Entities</h3>
        <ul className="mt-2 list-disc pl-5">
          {response.entities.map((entity) => (
            <li key={entity.id}>{entity.label}</li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="font-semibold">Graph preview</h3>
        {response.graphPreview ? (
          <p className="mt-2">
            Nodes: {response.graphPreview.nodes} · Edges: {response.graphPreview.edges}
          </p>
        ) : (
          <p className="mt-2 text-zinc-500">No graph preview available.</p>
        )}
      </section>

      <section>
        <h3 className="font-semibold">Trace</h3>
        <ul className="mt-2 space-y-1">
          {response.trace.map((trace, index) => (
            <li key={`${trace.step}-${index}`}>
              <span className="font-medium">{trace.step}:</span> {trace.detail}
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  async function sendQuery(nextQuery: string) {
    setLoading(true);
    setError(null);

    try {
      const response = await api.chat(nextQuery);

      setMessages((prev) => [
        ...prev,
        { role: 'user', content: nextQuery },
        { role: 'assistant', content: response.answer },
      ]);

      setLastResponse(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  const controls = useMemo(
    () => ({
      sendQuery,
      clear: () => {
        setMessages([]);
        setLastResponse(null);
        setError(null);
      },
      loading,
    }),
    [loading],
  );

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    controls.sendQuery(trimmed);
    setQuery('');
  }

  return (
    <main className="mx-auto grid max-w-6xl gap-6 p-6 md:grid-cols-[2fr_1fr]">
      <section className="space-y-4">
        <form onSubmit={onSubmit} className="flex gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="flex-1 rounded border px-3 py-2"
            placeholder="Frage stellen …"
          />
          <button disabled={loading} className="rounded bg-black px-4 py-2 text-white disabled:opacity-50">
            {loading ? 'Lädt…' : 'Senden'}
          </button>
          <button
            type="button"
            onClick={controls.clear}
            className="rounded border px-4 py-2"
            disabled={loading && messages.length === 0}
          >
            Reset
          </button>
        </form>

        {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-700">{error}</p>}

        <ul className="space-y-2">
          {messages.map((message, index) => (
            <li key={`${message.role}-${index}`} className="rounded border p-3">
              <p className="text-xs uppercase text-zinc-500">{message.role}</p>
              <p>{message.content}</p>
            </li>
          ))}
        </ul>
      </section>

      <RightPanel response={lastResponse} />
    </main>
  );
}
