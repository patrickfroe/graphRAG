export type ChatRequest = {
  query: string;
  session_id?: string;
  top_k?: number;
  graph_hops?: number;
  max_graph_nodes?: number;
  max_graph_edges?: number;
  entity_types?: string[];
  use_graph?: boolean;
  use_vector?: boolean;
  return_debug?: boolean;
};

export type Source = {
  source_id: string; // "S1"
  doc_id: string;
  chunk_id: string;
  score: number;
  title?: string;
  snippet: string;
  text?: string;
};

export type Entity = {
  key: string; // "ORG:neo4j"
  name: string; // "Neo4j"
  type: string; // "ORG"
  salience: number; // 0..1
  source_chunk_ids: string[];
};

export type GraphNode = {
  id: string;
  label: string;
  type: string;
  weight?: number;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  weight?: number;
  evidence_chunk_ids?: string[];
};

export type GraphPreview = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta?: {
    seed_entity_keys: string[];
    hops: number;
    truncated: boolean;
  };
};

export type ChatResponse = {
  answer: string;

  citations: Array<{
    marker: string;
    chunk_id: string;
    doc_id: string;
    score?: number;
  }>;

  sources: Source[];
  entities: Entity[];

  graph_evidence?: {
    seed_entity_keys: string[];

    facts?: Array<{
      fact_id: string;
      subject: string;
      predicate: string;
      object: string;
      evidence_chunk_ids: string[];
      confidence?: number;
    }>;

    preview?: GraphPreview;
  };

  trace?: {
    mode: "vector+graph" | "vector" | "graph";

    timings_ms?: Record<string, number>;

    retrieval?: {
      top_k: number;
      graph_hops: number;
      graph_nodes: number;
      graph_edges: number;
      context_tokens_est: number;
    };

    warnings?: string[];
  };
};
