"use client";

type EvidenceItem = {
  chunk_id: string;
  doc_id?: string;
  title?: string;
  text: string;
};

type EvidenceDrawerProps = {
  open: boolean;
  loading: boolean;
  error: string | null;
  items: EvidenceItem[];
  onClose: () => void;
};

export default function EvidenceDrawer({ open, loading, error, items, onClose }: EvidenceDrawerProps) {
  return (
    <aside
      className={`fixed right-0 top-0 z-40 h-full w-full max-w-lg transform border-l bg-white p-4 shadow-xl transition-transform ${
        open ? "translate-x-0" : "translate-x-full"
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Evidence</h2>
        <button type="button" className="rounded border px-3 py-1" onClick={onClose}>
          Schließen
        </button>
      </div>

      {loading && <p className="text-sm text-gray-500">Lade Evidence…</p>}
      {error && <p className="rounded border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</p>}

      <div className="mt-2 space-y-2 overflow-y-auto">
        {items.map((item) => (
          <article key={item.chunk_id} className="rounded border p-3">
            <p className="text-xs text-gray-500">{item.chunk_id}</p>
            <h3 className="font-medium">{item.title || item.doc_id || "Untitled"}</h3>
            <p className="mt-1 whitespace-pre-wrap text-sm text-gray-700">{item.text}</p>
          </article>
        ))}
      </div>
    </aside>
  );
}
