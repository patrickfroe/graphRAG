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

export type DocumentItem = {
  id: string;
  title: string;
  file_name: string;
  uploaded_at: string;
  chunk_count: number;
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
  return requestJson<DocumentItem[]>(`${API_BASE}/documents`, { method: "GET" });
}

export async function uploadDocument(file: File): Promise<{ id?: string }> {
  const formData = new FormData();
  formData.append("file", file);

  return requestJson<{ id?: string }>(`${API_BASE}/documents/upload`, {
    method: "POST",
    body: formData,
  });
}

export async function deleteDocument(documentId: string): Promise<{ deleted: boolean }> {
  return requestJson<{ deleted: boolean }>(`${API_BASE}/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function reindexDocument(documentId: string): Promise<{ reindexed: boolean }> {
  return requestJson<{ reindexed: boolean }>(`${API_BASE}/documents/${documentId}/reindex`, {
    method: "POST",
  });
}

export async function runQuery(payload: { query: string }): Promise<QueryResponse> {
  const response = await chat({ query: payload.query });
  return {
    answer: response.answer,
    sources: response.sources.map((source) => source.source_id || source.chunk_id),
  };
}
