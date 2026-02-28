# graphRAG UI

Next.js-Frontend für Chat, Ingest und Graph-Ansicht.

## Voraussetzungen

- Node.js 18+
- npm
- Laufendes Backend auf `http://localhost:8000`

## Installation

```bash
npm install
```

## Entwicklung starten

```bash
npm run dev
```

Danach öffnen:

- `http://localhost:3000/chat` (Hauptseite)
- `http://localhost:3000/ingest`
- `http://localhost:3000/graph`

## Produktionsbuild lokal prüfen

```bash
npm run typecheck
npm run build
npm run start
```

Dann ist das UI unter `http://localhost:3000` erreichbar.

## Backend-Anbindung

Das UI verwendet aktuell fest `http://localhost:8000` als API-Basis.

Verwendete Endpunkte:

- `POST /chat`
- `GET /graph/preview`
- `GET /evidence`

Wenn du lokal testest, stelle sicher, dass dein Backend diese Endpunkte bereitstellt.
