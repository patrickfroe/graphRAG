"use client";

import { ChangeEvent, useMemo, useState } from "react";

import { ingestDocuments } from "../../lib/api";

const ACCEPTED_FILE_TYPES = ".txt,.md,.csv,.json,text/plain,text/markdown,text/csv,application/json";

export default function IngestPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const totalSizeLabel = useMemo(() => {
    const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
    if (totalBytes < 1024) return `${totalBytes} B`;
    if (totalBytes < 1024 * 1024) return `${(totalBytes / 1024).toFixed(1)} KB`;
    return `${(totalBytes / (1024 * 1024)).toFixed(1)} MB`;
  }, [files]);

  const handleFilesChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    setFiles(selectedFiles);
    setError(null);
    setSuccess(null);
  };

  const handleUpload = async () => {
    if (files.length === 0 || loading) return;

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const contents = await Promise.all(files.map((file) => file.text()));
      const response = await ingestDocuments(contents);
      setSuccess(`${response.ingested} Datei(en) erfolgreich ingestiert.`);
      setFiles([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-2xl space-y-4 rounded border p-5">
      <h2 className="text-2xl font-semibold">Ingest</h2>
      <p className="text-muted-foreground">Lade Textdateien hoch, damit sie für den Chat indexiert werden.</p>

      <div className="space-y-2 rounded border border-dashed p-4">
        <label htmlFor="ingest-files" className="block text-sm font-medium">
          Dateien auswählen
        </label>
        <input
          id="ingest-files"
          type="file"
          multiple
          accept={ACCEPTED_FILE_TYPES}
          className="w-full text-sm"
          onChange={handleFilesChange}
          disabled={loading}
        />

        <p className="text-xs text-gray-500">Unterstützt: .txt, .md, .csv, .json</p>
      </div>

      {files.length > 0 && (
        <div className="space-y-2 rounded border p-3">
          <p className="text-sm font-medium">
            {files.length} Datei(en) ausgewählt · {totalSizeLabel}
          </p>
          <ul className="max-h-40 space-y-1 overflow-y-auto text-sm text-gray-700">
            {files.map((file) => (
              <li key={`${file.name}-${file.lastModified}`}>{file.name}</li>
            ))}
          </ul>
        </div>
      )}

      {error && <div className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div>}
      {success && <div className="rounded border border-green-200 bg-green-50 p-2 text-sm text-green-700">{success}</div>}

      <button
        type="button"
        className="rounded bg-black px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
        onClick={handleUpload}
        disabled={loading || files.length === 0}
      >
        {loading ? "Lade hoch..." : "Dateien ingestieren"}
      </button>
    </section>
  );
}
