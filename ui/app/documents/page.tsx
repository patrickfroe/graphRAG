"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Trash2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { ChangeEvent, useMemo, useRef, useState } from "react";

import { deleteDocument, listDocuments, reindexDocument, uploadDocument } from "../../lib/api";

const queryKey = ["documents"];

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

export default function DocumentsPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data: documents = [], isLoading, isError, error } = useQuery({
    queryKey,
    queryFn: listDocuments,
  });

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey });
      setActionError(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
    onError: (mutationError: Error) => {
      setActionError(mutationError.message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey });
      setActionError(null);
    },
    onError: (mutationError: Error) => {
      setActionError(mutationError.message);
    },
  });

  const reindexMutation = useMutation({
    mutationFn: reindexDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey });
      setActionError(null);
    },
    onError: (mutationError: Error) => {
      setActionError(mutationError.message);
    },
  });

  const isMutating = uploadMutation.isPending || deleteMutation.isPending || reindexMutation.isPending;

  const uploadingLabel = useMemo(() => (uploadMutation.isPending ? "Uploading..." : "Upload"), [uploadMutation.isPending]);

  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  const handleUpload = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || uploadMutation.isPending) {
      return;
    }

    uploadMutation.mutate(file);
  };

  const handleViewGraph = (documentId: string) => {
    window.localStorage.setItem("graph-seed-keys", JSON.stringify([documentId]));
    router.push("/graph");
  };

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold">Documents</h2>
          <p className="text-muted-foreground">Manage uploaded documents and indexing actions.</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded border px-3 py-2 text-sm"
            onClick={() => router.push("/graph/all")}
            disabled={isMutating}
          >
            Gesamten Graph ansehen
          </button>
          <div>
            <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} disabled={uploadMutation.isPending} />
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded bg-black px-4 py-2 text-white disabled:cursor-not-allowed disabled:opacity-50"
              onClick={handleSelectFile}
              disabled={uploadMutation.isPending}
            >
              {uploadMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              {uploadingLabel}
            </button>
          </div>
        </div>
      </div>

      {(isError || actionError) && (
        <p className="rounded border border-red-400 bg-red-50 p-2 text-sm text-red-700">
          {actionError ?? (error instanceof Error ? error.message : "Failed to load documents")}
        </p>
      )}

      <div className="overflow-x-auto rounded border">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2">title</th>
              <th className="px-3 py-2">file_name</th>
              <th className="px-3 py-2">uploaded_at</th>
              <th className="px-3 py-2">chunk_count</th>
              <th className="px-3 py-2">actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-center text-muted-foreground">
                  Loading documents...
                </td>
              </tr>
            )}

            {!isLoading && documents.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-center text-muted-foreground">
                  No documents found.
                </td>
              </tr>
            )}

            {documents.map((document) => (
              <tr key={document.id} className="border-t align-middle">
                <td className="px-3 py-2">{document.title}</td>
                <td className="px-3 py-2">{document.file_name}</td>
                <td className="px-3 py-2">{formatDate(document.uploaded_at)}</td>
                <td className="px-3 py-2">{document.chunk_count}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs"
                      onClick={() => deleteMutation.mutate(document.id)}
                      disabled={isMutating}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      delete
                    </button>
                    <button
                      type="button"
                      className="rounded border px-2 py-1 text-xs"
                      onClick={() => handleViewGraph(document.id)}
                      disabled={isMutating}
                    >
                      view graph
                    </button>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs"
                      onClick={() => reindexMutation.mutate(document.id)}
                      disabled={isMutating}
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      reindex
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
