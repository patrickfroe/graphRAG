'use client';

import { useCallback, useMemo, useState } from 'react';

type Role = 'user' | 'assistant';

type Message = {
  id: string;
  role: Role;
  content: string;
};

type Controls = {
  top_k: number;
  hops: number;
  temperature: number;
};

type ChatResponse = {
  answer: string;
  sources?: string[];
  metadata?: Record<string, unknown>;
};

const api = {
  async chat(payload: {
    query: string;
    messages: Message[];
    controls: Controls;
  }): Promise<ChatResponse> {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error('Chat request failed');
    }

    return response.json();
  },
};

function RightPanel({ data }: { data: ChatResponse | null }) {
  return (
    <aside>
      <h2>Last Response</h2>
      {!data ? (
        <p>No response yet.</p>
      ) : (
        <div>
          <p>{data.answer}</p>
          {data.sources?.length ? (
            <ul>
              {data.sources.map((source) => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
    </aside>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [controls, setControls] = useState<Controls>({
    top_k: 5,
    hops: 2,
    temperature: 0.2,
  });

  const canSend = useMemo(() => query.trim().length > 0 && !loading, [query, loading]);

  const sendQuery = useCallback(async () => {
    if (!query.trim() || loading) {
      return;
    }

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
    };

    const nextMessages = [...messages, userMessage];

    setMessages(nextMessages);
    setLoading(true);
    setError(null);

    try {
      const response = await api.chat({
        query,
        messages: nextMessages,
        controls,
      });

      setLastResponse(response);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: response.answer,
        },
      ]);
      setQuery('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [controls, loading, messages, query]);

  return (
    <main style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
      <section>
        <h1>Chat</h1>

        <div>
          <label>
            top_k
            <input
              type="number"
              value={controls.top_k}
              onChange={(event) =>
                setControls((prev) => ({ ...prev, top_k: Number(event.target.value) }))
              }
            />
          </label>
          <label>
            hops
            <input
              type="number"
              value={controls.hops}
              onChange={(event) =>
                setControls((prev) => ({ ...prev, hops: Number(event.target.value) }))
              }
            />
          </label>
          <label>
            temperature
            <input
              type="number"
              step="0.1"
              value={controls.temperature}
              onChange={(event) =>
                setControls((prev) => ({ ...prev, temperature: Number(event.target.value) }))
              }
            />
          </label>
        </div>

        <div>
          {messages.map((message) => (
            <p key={message.id}>
              <strong>{message.role}:</strong> {message.content}
            </p>
          ))}
        </div>

        <textarea
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ask something..."
        />

        <button disabled={!canSend} onClick={sendQuery}>
          {loading ? 'Sending...' : 'Send'}
        </button>

        {error ? <p style={{ color: 'red' }}>{error}</p> : null}
      </section>

      <RightPanel data={lastResponse} />
    </main>
  );
}
