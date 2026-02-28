export interface ChatRequest {
  [key: string]: unknown;
}

export interface ChatResponse {
  [key: string]: unknown;
}

export interface GraphPreview {
  [key: string]: unknown;
}

const JSON_HEADERS: HeadersInit = {
  'Content-Type': 'application/json',
};

async function postJson<TResponse>(path: string, body: unknown): Promise<TResponse> {
  const response = await fetch(path, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => '');
    throw new Error(
      `Request to ${path} failed (${response.status} ${response.statusText})${
        errorBody ? `: ${errorBody}` : ''
      }`,
    );
  }

  return (await response.json()) as TResponse;
}

export function chat(req: ChatRequest): Promise<ChatResponse> {
  return postJson<ChatResponse>('/api/chat', req);
}

export function graphPreview(seed_entity_keys: string[], hops = 1): Promise<GraphPreview> {
  return postJson<GraphPreview>('/api/graphPreview', { seed_entity_keys, hops });
}

export function evidence(chunk_ids: string[]): Promise<{ chunks: any[] }> {
  return postJson<{ chunks: any[] }>('/api/evidence', { chunk_ids });
}
