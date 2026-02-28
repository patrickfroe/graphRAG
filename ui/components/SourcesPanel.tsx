"use client";

import { forwardRef, useImperativeHandle, useRef } from "react";

import type { Source } from "../types";

export type SourcesPanelHandle = {
  scrollToSource: (sourceId: string) => void;
};

type SourcesPanelProps = {
  sources: Source[];
  activeSourceId?: string | null;
  onOpenEvidence?: (chunkId: string) => void;
};

const SourcesPanel = forwardRef<SourcesPanelHandle, SourcesPanelProps>(function SourcesPanel(
  { sources, activeSourceId, onOpenEvidence },
  ref,
) {
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useImperativeHandle(ref, () => ({
    scrollToSource: (sourceId: string) => {
      itemRefs.current[sourceId]?.scrollIntoView({ behavior: "smooth", block: "center" });
    },
  }));

  return (
    <div className="h-full overflow-y-auto rounded border p-3">
      <h2 className="mb-3 text-base font-semibold">Sources</h2>
      <div className="space-y-2">
        {sources.map((source) => (
          <div
            key={source.source_id}
            ref={(el) => {
              itemRefs.current[source.source_id] = el;
            }}
            className={`rounded border p-2 ${activeSourceId === source.source_id ? "border-blue-500 bg-blue-50" : ""}`}
          >
            <div className="mb-1 flex items-center justify-between gap-2 text-xs text-gray-500">
              <span className="font-semibold">[{source.source_id}]</span>
              <span>Score: {source.score.toFixed(3)}</span>
            </div>
            <p className="text-sm font-medium">{source.title || source.doc_id}</p>
            <p className="mt-1 text-sm text-gray-700">{source.snippet}</p>
            <button
              type="button"
              className="mt-2 text-xs text-blue-700 underline"
              onClick={() => onOpenEvidence?.(source.chunk_id)}
            >
              Evidence öffnen
            </button>
          </div>
        ))}
        {sources.length === 0 && <p className="text-sm text-gray-500">Keine Sources vorhanden.</p>}
      </div>
    </div>
  );
});

export default SourcesPanel;
