import type { ChatRequest, ChatResponse, GraphPreview } from "../types";

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

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: {
      "Content-Type": "application/json",
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
    params.set("seed_entity_keys", seedEntityKeys.join(","));
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
