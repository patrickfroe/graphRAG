"use client";

import { useEffect, useMemo, useState } from "react";

import GraphModal from "../../components/GraphModal";
import { graphPreview } from "../../lib/api";
import type { GraphPreview } from "../../types";

function parseSeedInput(input: string): string[] {
  return input
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

export default function GraphPage() {
  const [seedInput, setSeedInput] = useState("");
  const [showFullGraph, setShowFullGraph] = useState(false);
  const [preview, setPreview] = useState<GraphPreview | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    const savedPreviewRaw = window.localStorage.getItem("graph-preview");
    const savedSeedKeysRaw = window.localStorage.getItem("graph-seed-keys");

    if (savedSeedKeysRaw) {
      const parsedSeedKeys = JSON.parse(savedSeedKeysRaw) as string[];
      setSeedInput(parsedSeedKeys.join(", "));
    }

    if (savedPreviewRaw) {
      const parsedPreview = JSON.parse(savedPreviewRaw) as GraphPreview | null;
      if (parsedPreview) {
        setPreview(parsedPreview);
      }
    }
  }, []);

  const seedKeys = useMemo(() => parseSeedInput(seedInput), [seedInput]);

  const handleLoad = async () => {
    if (!showFullGraph && seedKeys.length === 0) {
      setError("Bitte Seed Keys eingeben oder 'Gesamten Graph laden' aktivieren.");
      setPreview(undefined);
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const requestSeedKeys = showFullGraph ? [] : seedKeys;
      const response = await graphPreview(requestSeedKeys);
      setPreview(response);
      setModalOpen(response.nodes.length > 0);
      window.localStorage.setItem("graph-preview", JSON.stringify(response));
      window.localStorage.setItem("graph-seed-keys", JSON.stringify(requestSeedKeys));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Graph preview failed");
      setPreview(undefined);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="space-y-4">
      <h2 className="text-2xl font-semibold">Graph</h2>
      <p className="text-muted-foreground">Lade eine Graph-Vorschau für Entity-Keys aus dem Chat oder gib eigene Keys ein.</p>

      <div className="space-y-2 rounded border p-3">
        <label className="block text-sm font-medium" htmlFor="seed-keys">
          Seed Entity Keys (comma-separated)
        </label>
        <input
          id="seed-keys"
          className="w-full rounded border px-3 py-2"
          value={seedInput}
          onChange={(event) => setSeedInput(event.target.value)}
          placeholder="ORG:neo4j, TECH:graph"
          disabled={showFullGraph}
        />
        <label className="inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showFullGraph}
            onChange={(event) => setShowFullGraph(event.target.checked)}
          />
          Gesamten Graph laden
        </label>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded bg-black px-3 py-1 text-white disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleLoad}
            disabled={loading}
          >
            {loading ? "Lade..." : "Graph laden"}
          </button>
          <button
            type="button"
            className="rounded border px-3 py-1"
            onClick={() => setModalOpen(true)}
            disabled={!preview || preview.nodes.length === 0}
          >
            Visualisierung öffnen
          </button>
        </div>
      </div>

      {error && <p className="rounded border border-red-400 bg-red-50 p-2 text-sm text-red-700">{error}</p>}

      <div className="rounded border p-3 text-sm">
        <p>
          Nodes: <strong>{preview?.nodes.length ?? 0}</strong> · Edges: <strong>{preview?.edges.length ?? 0}</strong>
        </p>
        {(preview?.nodes.length ?? 0) === 0 && (
          <p className="mt-2 text-muted-foreground">Keine Daten vorhanden. Bitte Seed Keys eingeben und Graph laden.</p>
        )}
      </div>

      <GraphModal open={modalOpen} preview={preview} onClose={() => setModalOpen(false)} />
    </section>
  );
}
