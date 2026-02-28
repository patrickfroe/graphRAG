"use client";

import type { Entity } from "../types";

type EntitiesPanelProps = {
  entities: Entity[];
};

export default function EntitiesPanel({ entities }: EntitiesPanelProps) {
  return (
    <div className="h-full overflow-y-auto rounded border p-3">
      <h2 className="mb-3 text-base font-semibold">Entities</h2>
      <div className="space-y-2">
        {entities.map((entity) => (
          <div key={entity.key} className="rounded border p-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold">{entity.name}</span>
              <span className="text-xs text-gray-500">{entity.type}</span>
            </div>
            <p className="text-xs text-gray-500">{entity.key}</p>
            <p className="mt-1 text-xs">Salience: {(entity.salience * 100).toFixed(0)}%</p>
          </div>
        ))}
        {entities.length === 0 && <p className="text-sm text-gray-500">Keine Entities verfügbar.</p>}
      </div>
    </div>
  );
}
