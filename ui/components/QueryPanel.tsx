"use client";

import { FormEvent, useState } from "react";
import { runQuery } from "@/lib/api";
import type { QueryResponse } from "@/types";

export function QueryPanel() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await runQuery({ query });
      setResult(response);
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Unknown error");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <form onSubmit={onSubmit} className="panel">
        <label htmlFor="query">Question</label>
        <textarea
          id="query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="How does product X relate to cluster Y?"
          required
        />
        <button type="submit" disabled={loading}>
          {loading ? "Running..." : "Run query"}
        </button>
      </form>

      {error ? <section className="result">Error: {error}</section> : null}
      {result ? (
        <section className="result">
          <h2>Answer</h2>
          <p>{result.answer}</p>
          <h3>Sources</h3>
          <ul>
            {result.sources.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
