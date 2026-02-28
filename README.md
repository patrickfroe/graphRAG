# graphRAG

Praktische Anleitung, um dieses Repository lokal zu starten (Python-API + optionales Next.js-UI).

## Projektstruktur (relevant zum Starten)

- `main.py`: einfache FastAPI-Demo mit `/ingest` und `/chat`
- `app.py`: FastAPI-Endpunkt `/graph/preview`
- `ui/`: Next.js Frontend (`/chat`, `/ingest`, `/graph`)

## Voraussetzungen

- Python **3.10+**
- Node.js **18+** (für das UI)
- npm

## 1) Python-Umgebung einrichten

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## 2) Backend starten

### Option A (empfohlen für Chat-Demo): `main.py`

Diese API bietet:
- `POST /ingest`
- `POST /chat`

Starten:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Schnelltest in zweitem Terminal:

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"documents":["FastAPI builds APIs quickly","GraphRAG uses retrieval"]}'

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What uses retrieval?"}'
```

### Option B (Graph-Preview einzeln): `app.py`

Diese API bietet:
- `GET /graph/preview?entity_keys=A,B,C`

Starten:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Schnelltest:

```bash
curl "http://localhost:8000/graph/preview?entity_keys=A,B,C"
```

## 3) Frontend starten (optional)

```bash
cd ui
npm install
npm run dev
```

Dann im Browser öffnen: `http://localhost:3000/chat`

> Hinweis: Das UI nutzt standardmäßig `http://localhost:8000` als API-Basis.

## 4) Empfohlene Checks

Backend:

```bash
pytest
```

Frontend:

```bash
cd ui
npm run typecheck
npm run build
```

## 5) OpenAI-Ressourcen (Embeddings + LLM)

Eine Schritt-für-Schritt-Anleitung zum Konfigurieren von OpenAI (`OPENAI_API_KEY`, Embedding-Modell, Chat-Modell) findest du hier:

- `docs/openai-ressourcen.md`

## 6) Milvus + Neo4j integrieren

Eine Schritt-für-Schritt-Anleitung für lokalen Start per Docker, `.env`-Konfiguration und Integrationstest (`/ingest`, `/chat`) findest du hier:

- `docs/milvus-neo4j-integration.md`

## Häufige Probleme

- **`ModuleNotFoundError` in Python**: sicherstellen, dass `.venv` aktiv ist und `pip install -r requirements.txt` ausgeführt wurde.
- **Port bereits belegt**: Backend auf anderem Port starten (z. B. `--port 8001`) und ggf. UI-Konfiguration anpassen.
- **UI kann Backend nicht erreichen**: prüfen, ob Backend wirklich auf `localhost:8000` läuft.
