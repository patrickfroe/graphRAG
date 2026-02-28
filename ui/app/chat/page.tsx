"use client";

import { useMemo, useRef, useState } from "react";

import ChatPanel, { type ChatMessage } from "../../components/ChatPanel";
import EntitiesPanel from "../../components/EntitiesPanel";
import EvidenceDrawer from "../../components/EvidenceDrawer";
import GraphModal from "../../components/GraphModal";
import SourcesPanel, { type SourcesPanelHandle } from "../../components/SourcesPanel";
import TracePanel from "../../components/TracePanel";
import { chat, evidence, graphPreview, type EvidenceResponse } from "../../lib/api";
import type { ChatResponse, GraphPreview } from "../../types";
import type { ChatControls } from "../../components/ControlsBar";

type TabKey = "sources" | "graph" | "trace";

const initialControls: ChatControls = {
  topK: 8,
  graphHops: 2,
  useGraph: true,
  useVector: true,
  returnDebug: true,
};

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>("sources");
  const [controls, setControls] = useState<ChatControls>(initialControls);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const [graphOpen, setGraphOpen] = useState(false);
  const [graphData, setGraphData] = useState<GraphPreview | undefined>(undefined);

  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [evidenceItems, setEvidenceItems] = useState<EvidenceResponse["chunks"]>([]);

  const sourcePanelRef = useRef<SourcesPanelHandle>(null);

  const latestResponse = useMemo<ChatResponse | undefined>(() => {
    return [...messages].reverse().find((message) => message.role === "assistant")?.response;
  }, [messages]);

  const handleSend = async (query: string) => {
    setLoading(true);
    setError(null);

    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: query }]);

    try {
      const response = await chat({
        query,
        top_k: controls.topK,
        graph_hops: controls.graphHops,
        use_graph: controls.useGraph,
        use_vector: controls.useVector,
        return_debug: controls.returnDebug,
      });

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          response,
        },
      ]);

      setGraphData(response.graph_evidence?.preview);
      window.localStorage.setItem("graph-preview", JSON.stringify(response.graph_evidence?.preview ?? null));
      window.localStorage.setItem(
        "graph-seed-keys",
        JSON.stringify(response.graph_evidence?.seed_entity_keys ?? []),
      );
      setActiveTab("sources");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCitationClick = (sourceId: string) => {
    setActiveTab("sources");
    setActiveSourceId(sourceId);
    requestAnimationFrame(() => {
      sourcePanelRef.current?.scrollToSource(sourceId);
    });
  };

  const handleOpenEvidence = async (chunkId: string) => {
    setEvidenceOpen(true);
    setEvidenceLoading(true);
    setEvidenceError(null);

    try {
      const response = await evidence([chunkId]);
      setEvidenceItems(response.chunks ?? response.items ?? []);
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Evidence request failed");
      setEvidenceItems([]);
    } finally {
      setEvidenceLoading(false);
    }
  };

  const handleLoadGraph = async () => {
    const seedKeys = latestResponse?.graph_evidence?.seed_entity_keys ?? [];
    if (seedKeys.length === 0) {
      setError("Keine seed_entity_keys verfügbar.");
      return;
    }

    setError(null);
    try {
      const preview = await graphPreview(seedKeys);
      setGraphData(preview);
      setGraphOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Graph preview failed");
    }
  };

  return (
    <main className="grid h-screen grid-cols-1 gap-3 p-3 lg:grid-cols-[1.2fr_1fr]">
      <ChatPanel
        messages={messages}
        loading={loading}
        error={error}
        controls={controls}
        onControlsChange={setControls}
        onSend={handleSend}
        onCitationClick={handleCitationClick}
      />

      <section className="flex h-full flex-col rounded border p-3">
        <div className="mb-3 flex gap-2">
          {(
            [
              ["sources", "Sources"],
              ["graph", "Graph"],
              ["trace", "Trace"],
            ] as Array<[TabKey, string]>
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={`rounded border px-3 py-1 text-sm ${activeTab === key ? "bg-black text-white" : ""}`}
              onClick={() => setActiveTab(key)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-hidden">
          {activeTab === "sources" && (
            <div className="grid h-full grid-cols-1 gap-3 xl:grid-cols-2">
              <SourcesPanel
                ref={sourcePanelRef}
                sources={latestResponse?.sources ?? []}
                activeSourceId={activeSourceId}
                onOpenEvidence={handleOpenEvidence}
              />
              <EntitiesPanel entities={latestResponse?.entities ?? []} />
            </div>
          )}

          {activeTab === "graph" && (
            <div className="space-y-3 rounded border p-3">
              <p className="text-sm text-gray-600">
                Nodes: {graphData?.nodes.length ?? 0} · Edges: {graphData?.edges.length ?? 0}
              </p>
              <button type="button" className="rounded bg-black px-3 py-1 text-white" onClick={handleLoadGraph}>
                Graph Preview öffnen
              </button>
            </div>
          )}

          {activeTab === "trace" && <TracePanel trace={latestResponse?.trace} />}
        </div>
      </section>

      <GraphModal open={graphOpen} preview={graphData} onClose={() => setGraphOpen(false)} />

      <EvidenceDrawer
        open={evidenceOpen}
        loading={evidenceLoading}
        error={evidenceError}
        items={evidenceItems ?? []}
        onClose={() => setEvidenceOpen(false)}
      />
    </main>
  );
}
