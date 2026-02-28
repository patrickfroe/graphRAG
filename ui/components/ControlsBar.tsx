"use client";

import { useMemo } from "react";

export type ChatControls = {
  topK: number;
  graphHops: number;
  useGraph: boolean;
  useVector: boolean;
  returnDebug: boolean;
};

type ControlsBarProps = {
  controls: ChatControls;
  disabled?: boolean;
  onChange: (next: ChatControls) => void;
};

export default function ControlsBar({ controls, disabled, onChange }: ControlsBarProps) {
  const update = <K extends keyof ChatControls>(key: K, value: ChatControls[K]) => {
    onChange({ ...controls, [key]: value });
  };

  const modeLabel = useMemo(() => {
    if (controls.useGraph && controls.useVector) return "Hybrid";
    if (controls.useGraph) return "Graph";
    if (controls.useVector) return "Vector";
    return "None";
  }, [controls.useGraph, controls.useVector]);

  return (
    <div className="flex flex-wrap gap-3 rounded border p-3 text-sm">
      <label className="flex items-center gap-2">
        Top K
        <input
          type="number"
          min={1}
          className="w-16 rounded border px-2 py-1"
          value={controls.topK}
          disabled={disabled}
          onChange={(e) => update("topK", Number(e.target.value) || 1)}
        />
      </label>
      <label className="flex items-center gap-2">
        Graph Hops
        <input
          type="number"
          min={1}
          className="w-16 rounded border px-2 py-1"
          value={controls.graphHops}
          disabled={disabled}
          onChange={(e) => update("graphHops", Number(e.target.value) || 1)}
        />
      </label>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={controls.useVector}
          disabled={disabled}
          onChange={(e) => update("useVector", e.target.checked)}
        />
        Vector
      </label>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={controls.useGraph}
          disabled={disabled}
          onChange={(e) => update("useGraph", e.target.checked)}
        />
        Graph
      </label>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={controls.returnDebug}
          disabled={disabled}
          onChange={(e) => update("returnDebug", e.target.checked)}
        />
        Trace
      </label>

      <div className="ml-auto text-xs text-gray-500">Mode: {modeLabel}</div>
    </div>
  );
}
