const BASE_URL = "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(`API request failed (${response.status}): ${message}`);
  }

  return response.json() as Promise<T>;
}

export function chat(query: string) {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export function ingest() {
  return request("/ingest", {
    method: "POST",
  });
}

export function getGraphPreview(entityKeys?: string[]) {
  return request("/graph-preview", {
    method: "POST",
    body: JSON.stringify(
      entityKeys && entityKeys.length > 0 ? { entity_keys: entityKeys } : {}
    ),
  });
}

export { BASE_URL };
