import ForceGraph2D from 'react-force-graph';

type GraphNode = {
  id: string | number;
  type?: string;
  [key: string]: unknown;
};

type GraphEdge = {
  source: string | number | GraphNode;
  target: string | number | GraphNode;
  [key: string]: unknown;
};

type GraphViewerProps = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

const DEFAULT_NODE_COLOR = '#3b82f6';

const NODE_TYPE_COLORS: Record<string, string> = {
  person: '#ef4444',
  company: '#10b981',
  location: '#f59e0b',
  event: '#8b5cf6'
};

const getNodeColor = (node: GraphNode): string => {
  if (!node.type) {
    return DEFAULT_NODE_COLOR;
  }

  return NODE_TYPE_COLORS[node.type] ?? DEFAULT_NODE_COLOR;
};

export const GraphViewer = ({ nodes, edges }: GraphViewerProps) => {
  return (
    <ForceGraph2D
      graphData={{ nodes, links: edges }}
      nodeLabel="id"
      nodeAutoColorBy="type"
      nodeCanvasObject={(node, ctx, globalScale) => {
        const graphNode = node as GraphNode;
        const label = String(graphNode.id);
        const fontSize = 12 / globalScale;

        ctx.fillStyle = getNodeColor(graphNode);
        ctx.beginPath();
        ctx.arc(node.x ?? 0, node.y ?? 0, 5, 0, 2 * Math.PI, false);
        ctx.fill();

        ctx.font = `${fontSize}px Sans-Serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = '#111827';
        ctx.fillText(label, node.x ?? 0, (node.y ?? 0) + 7);
      }}
    />
  );
};

export default GraphViewer;
