"use client";

import type { ChatResponse } from "../types";

type TracePanelProps = {
  trace?: ChatResponse["trace"];
};

export default function TracePanel({ trace }: TracePanelProps) {
  if (!trace) {
    return <div className="rounded border p-3 text-sm text-gray-500">Keine Trace-Daten vorhanden.</div>;
  }

  return (
    <div className="space-y-3 rounded border p-3 text-sm">
      <div>
        <h3 className="font-semibold">Mode</h3>
        <p>{trace.mode}</p>
      </div>

      {trace.timings_ms && (
        <div>
          <h3 className="font-semibold">Timings (ms)</h3>
          <ul className="list-inside list-disc">
            {Object.entries(trace.timings_ms).map(([key, value]) => (
              <li key={key}>
                {key}: {value}
              </li>
            ))}
          </ul>
        </div>
      )}

      {trace.retrieval && (
        <div>
          <h3 className="font-semibold">Retrieval</h3>
          <pre className="overflow-x-auto rounded bg-gray-50 p-2">{JSON.stringify(trace.retrieval, null, 2)}</pre>
        </div>
      )}

      {trace.warnings && trace.warnings.length > 0 && (
        <div>
          <h3 className="font-semibold">Warnings</h3>
          <ul className="list-inside list-disc text-amber-700">
            {trace.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
