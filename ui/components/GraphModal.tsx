"use client";

import dynamic from "next/dynamic";

import type { GraphPreview } from "../types";

const ForceGraph2D = dynamic(() => import("react-force-graph").then((mod) => mod.ForceGraph2D), {
  ssr: false,
});

type GraphModalProps = {
  open: boolean;
  preview?: GraphPreview;
  onClose: () => void;
};

export default function GraphModal({ open, preview, onClose }: GraphModalProps) {
  if (!open) return null;

  const graphData = {
    nodes: (preview?.nodes ?? []).map((node) => ({ ...node, name: node.label })),
    links: (preview?.edges ?? []).map((edge) => ({ ...edge })),
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-[80vh] w-full max-w-5xl flex-col rounded bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Graph Preview</h2>
          <button type="button" className="rounded border px-3 py-1" onClick={onClose}>
            Schließen
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden rounded border">
          <ForceGraph2D
            graphData={graphData}
            nodeLabel="name"
            linkLabel="label"
            nodeAutoColorBy="type"
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
          />
        </div>
      </div>
    </div>
  );
}
