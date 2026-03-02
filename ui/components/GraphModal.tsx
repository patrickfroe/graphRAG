"use client";

import type { GraphPreview } from "../types";

type GraphModalProps = {
  open: boolean;
  preview?: GraphPreview;
  onClose: () => void;
};

type PositionedNode = {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
};

const GRAPH_WIDTH = 960;
const GRAPH_HEIGHT = 560;
const NODE_RADIUS = 12;

const NODE_COLORS: Record<string, string> = {
  person: "#ef4444",
  company: "#10b981",
  location: "#f59e0b",
  event: "#8b5cf6",
};

function buildPositionedNodes(preview?: GraphPreview): PositionedNode[] {
  const nodes = preview?.nodes ?? [];

  if (nodes.length === 0) {
    return [];
  }

  const centerX = GRAPH_WIDTH / 2;
  const centerY = GRAPH_HEIGHT / 2;
  const radius = Math.min(GRAPH_WIDTH, GRAPH_HEIGHT) * 0.34;

  return nodes.map((node, index) => {
    const angle = (index / nodes.length) * Math.PI * 2;

    return {
      id: node.id,
      label: node.label,
      type: node.type,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    };
  });
}

export default function GraphModal({ open, preview, onClose }: GraphModalProps) {
  if (!open) return null;

  const nodes = buildPositionedNodes(preview);
  const edges = preview?.edges ?? [];
  const nodeLookup = new Map(nodes.map((node) => [node.id, node]));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="flex h-[80vh] w-full max-w-5xl flex-col rounded bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Graph Preview</h2>
          <button type="button" className="rounded border px-3 py-1" onClick={onClose}>
            Schließen
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto rounded border bg-slate-50 p-3">
          {nodes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Keine Graph-Daten vorhanden.</p>
          ) : (
            <svg
              viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
              className="h-full w-full min-w-[600px]"
              role="img"
              aria-label="Graph preview"
            >
              {edges.map((edge) => {
                const source = nodeLookup.get(edge.source);
                const target = nodeLookup.get(edge.target);

                if (!source || !target) {
                  return null;
                }

                return (
                  <g key={edge.id}>
                    <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="#94a3b8" strokeWidth={1.5} />
                    <text
                      x={(source.x + target.x) / 2}
                      y={(source.y + target.y) / 2}
                      fontSize="10"
                      fill="#475569"
                      textAnchor="middle"
                    >
                      {edge.label}
                    </text>
                  </g>
                );
              })}

              {nodes.map((node) => (
                <g key={node.id}>
                  <circle cx={node.x} cy={node.y} r={NODE_RADIUS} fill={NODE_COLORS[node.type.toLowerCase()] ?? "#3b82f6"} />
                  <text x={node.x} y={node.y + NODE_RADIUS + 14} fontSize="12" fill="#0f172a" textAnchor="middle">
                    {node.label}
                  </text>
                </g>
              ))}
            </svg>
          )}
        </div>
      </div>
    </div>
  );
}
