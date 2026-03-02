import type { ChatRequest, ChatResponse, GraphPreview, QueryResponse } from "../types";

const API_BASE = "http://localhost:8000";

export type EvidenceResponse = {
  chunks?: Array<{
    chunk_id: string;
    doc_id?: string;
    title?: string;
    text: string;
  }>;
  items?: Array<{
    chunk_id: string;
    doc_id?: string;
    title?: string;
    text: string;
  }>;
};

export type DocumentGraphNode = {
  id: string;
  label: string;
  type: string;
  [key: string]: unknown;
};

export type DocumentGraphEdge = {
  source: string;
  target: string;
  label?: string;
  [key: string]: unknown;
};

export type DocumentGraphResponse = {
  nodes: DocumentGraphNode[];
  edges: DocumentGraphEdge[];
};

type DocumentApiItem = {
  doc_id: string;
  title: string;
  file_name: string;
  uploaded_at: string;
  chunk_count: number;
  extracted_entity_count?: number;
  extracted_entities?: Array<{
    key: string;
    name: string;
    type: string;
    mentions: number;
  }>;
};

export type DocumentItem = {
  id: string;
  title: string;
  file_name: string;
  uploaded_at: string;
  chunk_count: number;
  extracted_entity_count: number;
  extracted_entities: Array<{
    key: string;
    name: string;
    type: string;
    mentions: number;
  }>;
};

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const hasFormDataBody = init?.body instanceof FormData;
  const response = await fetch(input, {
    ...init,
    headers: {
      ...(hasFormDataBody ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function chat(payload: ChatRequest): Promise<ChatResponse> {
  return requestJson<ChatResponse>(`${API_BASE}/chat`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function graphPreview(seedEntityKeys: string[]): Promise<GraphPreview> {
  const params = new URLSearchParams();
  if (seedEntityKeys.length > 0) {
    params.set("entity_keys", seedEntityKeys.join(","));
  }

  return requestJson<GraphPreview>(`${API_BASE}/graph/preview?${params.toString()}`, {
    method: "GET",
  });
}

export async function evidence(chunkIds: string[]): Promise<EvidenceResponse> {
  const params = new URLSearchParams();
  if (chunkIds.length > 0) {
    params.set("chunk_ids", chunkIds.join(","));
  }

  return requestJson<EvidenceResponse>(`${API_BASE}/evidence?${params.toString()}`, {
    method: "GET",
  });
}

export async function graphDocument(docId: string): Promise<DocumentGraphResponse> {
  return requestJson<DocumentGraphResponse>(`${API_BASE}/graph/document/${encodeURIComponent(docId)}`, {
    method: "GET",
  });
}

export async function ingestDocuments(documents: string[]): Promise<{ ingested: number }> {
  const trimmedDocuments = documents.map((document) => document.trim()).filter(Boolean);

  if (trimmedDocuments.length === 0) {
    return { ingested: 0 };
  }

  try {
    return await requestJson<{ ingested: number }>(`${API_BASE}/ingest`, {
      method: "POST",
      body: JSON.stringify({
        documents: trimmedDocuments.map((text, index) => ({
          id: `upload-${Date.now()}-${index + 1}`,
          title: `Upload ${index + 1}`,
          text,
        })),
      }),
    });
  } catch {
    return requestJson<{ ingested: number }>(`${API_BASE}/ingest`, {
      method: "POST",
      body: JSON.stringify({ documents: trimmedDocuments }),
    });
  }
}

export async function listDocuments(): Promise<DocumentItem[]> {
  const documents = await requestJson<DocumentApiItem[]>(`${API_BASE}/documents`, { method: "GET" });
  return documents.map((document) => ({
    id: document.doc_id,
    title: document.title,
    file_name: document.file_name,
    uploaded_at: document.uploaded_at,
    chunk_count: document.chunk_count,
    extracted_entity_count: document.extracted_entity_count ?? 0,
    extracted_entities: document.extracted_entities ?? [],
  }));
}

type EntityExtractionConfig = {
  entityTypes?: string[];
};

export async function uploadDocument(file: File, config: EntityExtractionConfig = {}): Promise<DocumentApiItem> {
  const formData = new FormData();
  formData.append("file", file);
  if (config.entityTypes && config.entityTypes.length > 0) {
    formData.append("entity_types", JSON.stringify(config.entityTypes));
  }

  return requestJson<DocumentApiItem>(`${API_BASE}/documents/upload`, {
    method: "POST",
    body: formData,
  });
}

export async function deleteDocument(documentId: string): Promise<{ status: string; doc_id: string }> {
  return requestJson<{ status: string; doc_id: string }>(`${API_BASE}/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function reindexDocument(documentId: string, config: EntityExtractionConfig = {}): Promise<{ reindexed: boolean }> {
  return requestJson<{ reindexed: boolean }>(`${API_BASE}/documents/${documentId}/reindex`, {
    method: "POST",
    body: JSON.stringify(
      config.entityTypes && config.entityTypes.length > 0
        ? { entity_types: config.entityTypes }
        : {},
    ),
  });
}

export async function runQuery(payload: { query: string }): Promise<QueryResponse> {
  const response = await chat({ query: payload.query });
  return {
    answer: response.answer,
    sources: response.sources.map((source) => source.source_id || source.chunk_id),
  };
}
