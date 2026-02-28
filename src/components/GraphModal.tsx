import { useEffect, useMemo, useState } from 'react';

export type GraphNode = {
  id: string;
  label?: string;
  evidenceId?: string;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  label?: string;
  evidenceId?: string;
};

export type GraphPreview = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type GraphResponse = {
  graph_evidence?: {
    preview?: GraphPreview;
  };
};

export type EvidenceSelection =
  | { type: 'node'; node: GraphNode }
  | { type: 'edge'; edge: GraphEdge };

export type GraphModalProps = {
  response: GraphResponse;
  graphPreview: () => Promise<GraphPreview>;
  openEvidenceDrawer: (selection: EvidenceSelection) => void;
};

/**
 * GraphModal wiring:
 * - initial graph = response.graph_evidence.preview
 * - node click -> evidence drawer
 * - edge click -> evidence drawer
 * - expand button -> graphPreview()
 */
export function GraphModal({ response, graphPreview, openEvidenceDrawer }: GraphModalProps) {
  const initialGraph = useMemo(
    () => response.graph_evidence?.preview ?? { nodes: [], edges: [] },
    [response],
  );

  const [graph, setGraph] = useState<GraphPreview>(initialGraph);
  const [isExpanding, setIsExpanding] = useState(false);

  useEffect(() => {
    setGraph(initialGraph);
  }, [initialGraph]);

  const onExpand = async () => {
    setIsExpanding(true);
    try {
      const expandedGraph = await graphPreview();
      setGraph(expandedGraph);
    } finally {
      setIsExpanding(false);
    }
  };

  return (
    <section aria-label="Graph modal">
      <header>
        <h2>Graph</h2>
        <button type="button" onClick={onExpand} disabled={isExpanding}>
          {isExpanding ? 'Expanding…' : 'Expand'}
        </button>
      </header>

      <div>
        <h3>Nodes</h3>
        <ul>
          {graph.nodes.map((node) => (
            <li key={node.id}>
              <button
                type="button"
                onClick={() => openEvidenceDrawer({ type: 'node', node })}
              >
                {node.label ?? node.id}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h3>Edges</h3>
        <ul>
          {graph.edges.map((edge) => (
            <li key={edge.id}>
              <button
                type="button"
                onClick={() => openEvidenceDrawer({ type: 'edge', edge })}
              >
                {edge.label ?? `${edge.source} → ${edge.target}`}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
