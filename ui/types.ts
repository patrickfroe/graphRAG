export interface QueryRequest {
  query: string;
}

export interface QueryResponse {
  answer: string;
  sources: string[];
}
