"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Trash2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { ChangeEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import { deleteDocument, listDocuments, reindexDocument, uploadDocument } from "../../lib/api";

const queryKey = ["documents"];
const ENTITY_TYPES_STORAGE_KEY = "documents-entity-types";
const DEFAULT_ENTITY_TYPES = ["ORG", "PERSON", "PRODUCT", "TECH", "LOCATION"];

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
  const [entityTypeInput, setEntityTypeInput] = useState("");
  const [entityTypes, setEntityTypes] = useState<string[]>(DEFAULT_ENTITY_TYPES);

  useEffect(() => {
    const storedValue = window.localStorage.getItem(ENTITY_TYPES_STORAGE_KEY);
    if (!storedValue) {
      return;
    }

    try {
      const parsed = JSON.parse(storedValue);
      if (Array.isArray(parsed) && parsed.every((value) => typeof value === "string")) {
        setEntityTypes(parsed.map((value) => value.trim()).filter(Boolean));
      }
    } catch {
      // Ignore invalid local storage value and keep defaults.
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(ENTITY_TYPES_STORAGE_KEY, JSON.stringify(entityTypes));
  }, [entityTypes]);

  const { data: documents = [], isLoading, isError, error } = useQuery({
    queryKey,
    queryFn: listDocuments,
  });

  const uploadMutation = useMutation({
    mutationFn: ({ file, configuredEntityTypes }: { file: File; configuredEntityTypes: string[] }) =>
      uploadDocument(file, { entityTypes: configuredEntityTypes }),
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
    mutationFn: ({ documentId, configuredEntityTypes }: { documentId: string; configuredEntityTypes: string[] }) =>
      reindexDocument(documentId, { entityTypes: configuredEntityTypes }),
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

    uploadMutation.mutate({ file, configuredEntityTypes: entityTypes });
  };

  const addEntityType = () => {
    const normalizedEntityType = entityTypeInput.trim().toUpperCase();
    if (!normalizedEntityType || entityTypes.includes(normalizedEntityType)) {
      setEntityTypeInput("");
      return;
    }

    setEntityTypes((current) => [...current, normalizedEntityType]);
    setEntityTypeInput("");
  };

  const handleEntityTypeInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addEntityType();
    }
  };

  const removeEntityType = (entityTypeToRemove: string) => {
    setEntityTypes((current) => current.filter((entityType) => entityType !== entityTypeToRemove));
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

      <div className="space-y-3 rounded border p-4">
        <div>
          <h3 className="text-sm font-semibold">Entity extraction</h3>
          <p className="text-sm text-muted-foreground">Configure once which entity types should be extracted for uploads and reindexing.</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {entityTypes.length === 0 && <span className="text-sm text-muted-foreground">No entity types configured.</span>}
          {entityTypes.map((entityType) => (
            <span key={entityType} className="inline-flex items-center gap-2 rounded-full border px-2 py-1 text-xs">
              {entityType}
              <button
                type="button"
                className="font-semibold text-muted-foreground hover:text-foreground"
                onClick={() => removeEntityType(entityType)}
                disabled={isMutating}
                aria-label={`Remove entity type ${entityType}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={entityTypeInput}
            onChange={(event) => setEntityTypeInput(event.target.value)}
            onKeyDown={handleEntityTypeInputKeyDown}
            placeholder="Add entity type (e.g. EVENT)"
            className="min-w-[220px] flex-1 rounded border px-3 py-2 text-sm"
            disabled={isMutating}
          />
          <button type="button" className="rounded border px-3 py-2 text-sm" onClick={addEntityType} disabled={isMutating}>
            Add type
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded border">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2">title</th>
              <th className="px-3 py-2">file_name</th>
              <th className="px-3 py-2">uploaded_at</th>
              <th className="px-3 py-2">chunk_count</th>
              <th className="px-3 py-2">entities</th>
              <th className="px-3 py-2">actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-muted-foreground">
                  Loading documents...
                </td>
              </tr>
            )}

            {!isLoading && documents.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-center text-muted-foreground">
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
                  <div className="space-y-1">
                    <div className="text-xs font-medium">{document.extracted_entity_count} found</div>
                    {document.extracted_entities.length > 0 ? (
                      <div className="flex max-w-[360px] flex-wrap gap-1">
                        {document.extracted_entities.slice(0, 6).map((entity) => (
                          <span key={entity.key} className="rounded-full border px-2 py-0.5 text-[10px]">
                            {entity.name} <span className="text-muted-foreground">({entity.type}, {entity.mentions})</span>
                          </span>
                        ))}
                        {document.extracted_entities.length > 6 && (
                          <span className="text-[10px] text-muted-foreground">+{document.extracted_entities.length - 6} more</span>
                        )}
                      </div>
                    ) : (
                      <div className="text-xs text-muted-foreground">No entities extracted yet.</div>
                    )}
                  </div>
                </td>
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
                      onClick={() =>
                        reindexMutation.mutate({
                          documentId: document.id,
                          configuredEntityTypes: entityTypes,
                        })
                      }
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
