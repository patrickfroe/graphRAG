"use client";

import { FormEvent, useState } from "react";

import type { ChatResponse } from "../types";
import ControlsBar, { type ChatControls } from "./ControlsBar";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
};

type ChatPanelProps = {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  controls: ChatControls;
  onControlsChange: (next: ChatControls) => void;
  onSend: (query: string) => void;
  onCitationClick: (sourceId: string) => void;
};

function renderWithCitations(
  text: string,
  markerToSource: Map<string, string>,
  onCitationClick: (sourceId: string) => void,
) {
  const parts = text.split(/(\[S\d+\])/g);
  return parts.map((part, idx) => {
    if (/^\[S\d+\]$/.test(part)) {
      const sourceId = markerToSource.get(part);
      if (sourceId) {
        return (
          <button
            type="button"
            key={`${part}-${idx}`}
            className="mx-0.5 rounded bg-blue-100 px-1 text-blue-700 underline"
            onClick={() => onCitationClick(sourceId)}
          >
            {part}
          </button>
        );
      }
    }

    return <span key={`${part}-${idx}`}>{part}</span>;
  });
}

export default function ChatPanel({
  messages,
  loading,
  error,
  controls,
  onControlsChange,
  onSend,
  onCitationClick,
}: ChatPanelProps) {
  const [query, setQuery] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;
    onSend(trimmed);
    setQuery("");
  };

  return (
    <section className="flex h-full flex-col gap-3 rounded border p-3">
      <h1 className="text-lg font-semibold">GraphRAG Chat</h1>

      <ControlsBar controls={controls} onChange={onControlsChange} disabled={loading} />

      <div className="flex-1 space-y-3 overflow-y-auto rounded border p-3">
        {messages.length === 0 && <p className="text-sm text-gray-500">Stelle eine Frage, um zu starten.</p>}

        {messages.map((message) => {
          if (message.role === "user") {
            return (
              <div key={message.id} className="ml-auto max-w-[85%] rounded bg-gray-100 p-2">
                <p className="text-xs font-medium text-gray-500">You</p>
                <p>{message.content}</p>
              </div>
            );
          }

          const markerMap = new Map(
            message.response?.citations.map((c) => [c.marker, message.response?.sources.find((s) => s.chunk_id === c.chunk_id)?.source_id ?? c.marker.slice(1, -1)]) ?? [],
          );

          return (
            <div key={message.id} className="mr-auto max-w-[95%] rounded bg-blue-50 p-2">
              <p className="text-xs font-medium text-blue-700">Assistant</p>
              <p className="whitespace-pre-wrap">
                {renderWithCitations(message.content, markerMap, onCitationClick)}
              </p>
            </div>
          );
        })}
      </div>

      {error && <div className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}

      <form className="flex gap-2" onSubmit={handleSubmit}>
        <input
          className="flex-1 rounded border px-3 py-2"
          placeholder="Frage zu deinen Dokumenten..."
          value={query}
          disabled={loading}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button
          type="submit"
          className="rounded bg-black px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
          disabled={loading || !query.trim()}
        >
          {loading ? "Lädt..." : "Senden"}
        </button>
      </form>
    </section>
  );
}
