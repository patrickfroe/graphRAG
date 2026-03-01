"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

import EvidenceDrawer from "@/components/EvidenceDrawer";
import { graphDocument } from "@/lib/api";

type GraphNode = {
  id: string;
  label: string;
  type: string;
  chunk_id?: string;
  text?: string;
  entity_key?: string;
  [key: string]: unknown;
};

type GraphLink = {
  id?: string;
  source: string;
  target: string;
  label?: string;
  [key: string]: unknown;
};

type GraphDocumentResponse = {
  nodes: GraphNode[];
  edges: GraphLink[];
};

type ForceNode = GraphNode & { name: string };

type ForceLink = GraphLink;

const ForceGraph2D = dynamic(() => import("react-force-graph").then((mod) => mod.ForceGraph2D), {
  ssr: false,
});

const NODE_COLORS: Record<string, string> = {
  Document: "#2563eb",
  Chunk: "#6b7280",
  Entity: "#f97316",
};

function nodeColorByType(type: string): string {
  return NODE_COLORS[type] ?? "#94a3b8";
}

function toNodeId(value: string | number | { id?: string } | undefined): string {
  if (typeof value === "object" && value !== null && "id" in value && typeof value.id === "string") {
    return value.id;
  }
  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }
  return "";
}

function findDocumentRoot(nodes: GraphNode[], docId: string): string | null {
  return (
    nodes.find((node) => node.type === "Document" && (node.id === docId || String(node.doc_id ?? "") === docId))?.id ??
    nodes.find((node) => node.type === "Document")?.id ??
    null
  );
}

function buildAdjacency(links: GraphLink[]): Map<string, Set<string>> {
  const adjacency = new Map<string, Set<string>>();

  for (const link of links) {
    const sourceId = toNodeId(link.source);
    const targetId = toNodeId(link.target);
    if (!sourceId || !targetId) continue;

    if (!adjacency.has(sourceId)) adjacency.set(sourceId, new Set<string>());
    if (!adjacency.has(targetId)) adjacency.set(targetId, new Set<string>());

    adjacency.get(sourceId)?.add(targetId);
    adjacency.get(targetId)?.add(sourceId);
  }

  return adjacency;
}

function visibleNodeIds(rootId: string | null, adjacency: Map<string, Set<string>>, depth: number): Set<string> {
  if (!rootId) return new Set<string>();

  const visited = new Set<string>([rootId]);
  let frontier = new Set<string>([rootId]);

  for (let hop = 0; hop < depth; hop += 1) {
    const next = new Set<string>();
    for (const nodeId of frontier) {
      const neighbors = adjacency.get(nodeId);
      if (!neighbors) continue;
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          next.add(neighbor);
        }
      }
    }
    frontier = next;
    if (frontier.size === 0) break;
  }

  return visited;
}

export default function GraphViewerPage({ params }: { params: { doc_id: string } }) {
  const docId = params.doc_id;
  const [graph, setGraph] = useState<GraphDocumentResponse>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [depth, setDepth] = useState(1);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerItems, setDrawerItems] = useState<Array<{ chunk_id: string; title?: string; text: string }>>([]);

  useEffect(() => {
    void (async () => {
      try {
        const data = await graphDocument(docId);
        setGraph(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Graph konnte nicht geladen werden");
      } finally {
        setLoading(false);
      }
    })();
  }, [docId]);

  const adjacency = useMemo(() => buildAdjacency(graph.edges), [graph.edges]);
  const rootId = useMemo(() => findDocumentRoot(graph.nodes, docId), [graph.nodes, docId]);

  const visibleIds = useMemo(() => visibleNodeIds(rootId, adjacency, depth), [rootId, adjacency, depth]);

  const graphData = useMemo(() => {
    const visibleNodes = graph.nodes.filter((node) => visibleIds.has(node.id));
    const visibleLinks = graph.edges.filter((edge) => {
      const source = toNodeId(edge.source);
      const target = toNodeId(edge.target);
      return visibleIds.has(source) && visibleIds.has(target);
    });

    return {
      nodes: visibleNodes.map((node) => ({ ...node, name: node.label })) as ForceNode[],
      links: visibleLinks as ForceLink[],
    };
  }, [graph.nodes, graph.edges, visibleIds]);

  const maxDepthReached = useMemo(() => {
    if (!rootId) return true;
    const nextVisible = visibleNodeIds(rootId, adjacency, depth + 1);
    return nextVisible.size === visibleIds.size;
  }, [rootId, adjacency, depth, visibleIds]);

  const handleNodeClick = (node: ForceNode) => {
    if (node.type === "Chunk") {
      setDrawerItems([
        {
          chunk_id: node.chunk_id ?? node.id,
          title: node.label,
          text: String(node.text ?? "Kein Chunk-Text verfügbar."),
        },
      ]);
    } else if (node.type === "Entity") {
      const info = [
        `Entity: ${node.label}`,
        node.entity_key ? `Key: ${node.entity_key}` : null,
        node.text ? `Info: ${node.text}` : null,
      ]
        .filter(Boolean)
        .join("\n");

      setDrawerItems([
        {
          chunk_id: node.id,
          title: "Entity",
          text: info || "Keine Entity-Informationen verfügbar.",
        },
      ]);
    } else {
      setDrawerItems([
        {
          chunk_id: node.id,
          title: node.label,
          text: `Typ: ${node.type}`,
        },
      ]);
    }

    setDrawerOpen(true);
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Graph Viewer: {docId}</h2>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded border px-3 py-1 disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => setDepth((current) => current + 1)}
            disabled={loading || !!error || maxDepthReached}
          >
            Expand 1 hop
          </button>
          <button
            type="button"
            className="rounded border px-3 py-1"
            onClick={() => setDepth(1)}
            disabled={loading || !!error}
          >
            Reset graph
          </button>
        </div>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Lade Graph…</p>}
      {error && <p className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">{error}</p>}

      <div className="h-[70vh] overflow-hidden rounded border">
        <ForceGraph2D
          graphData={graphData}
          nodeLabel="name"
          linkLabel="label"
          nodeColor={(node) => nodeColorByType((node as ForceNode).type)}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          onNodeClick={(node) => handleNodeClick(node as ForceNode)}
        />
      </div>

      <EvidenceDrawer
        open={drawerOpen}
        loading={false}
        error={null}
        items={drawerItems}
        onClose={() => setDrawerOpen(false)}
      />
    </section>
  );
}
