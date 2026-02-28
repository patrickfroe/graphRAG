# Anleitung: Milvus + Neo4j in GraphRAG integrieren

Diese Anleitung zeigt dir, wie du in diesem Projekt **Milvus** (Vektorsuche) und **Neo4j** (Knowledge Graph) lokal startest, konfigurierst und mit dem Backend verbindest.

## 1) Architektur im Projekt

- **Milvus** speichert Embeddings und liefert Similarity-Suche für Retrieval.
- **Neo4j** speichert Dokumentknoten und Beziehungen für graphbasierte Kontexte.

Im Code sind beide bereits vorbereitet:
- Konfiguration über Umgebungsvariablen in `app/config.py`
- Milvus-Anbindung in `app/vectorstore.py`
- Neo4j-Anbindung in `app/graph.py`

## 2) Services lokal starten (Docker Compose)

Im Repository liegt eine fertige Compose-Datei unter `docker/docker-compose.yml`.

Starten:

```bash
cd docker
docker compose up -d
```

Status prüfen:

```bash
docker compose ps
```

Erwartete Services:
- `graphrag-neo4j` (Ports `7474`, `7687`)
- `milvus-standalone` (Port `19530`)
- `milvus-etcd`
- `milvus-minio`

## 3) Backend-Konfiguration via `.env`

Lege im Projektroot eine `.env` an (oder ergänze sie):

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=documents

# Retrieval
TOP_K=5
```

> Die Default-Werte im Code entsprechen bereits der Compose-Konfiguration.

## 4) Backend starten

```bash
uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

## 5) Integration testen

### 5.1 Ingest ausführen (schreibt nach Milvus + Neo4j)

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {"doc_id":"doc-1","title":"GraphRAG Intro","text":"GraphRAG kombiniert Vektorsuche und Knowledge Graph."},
      {"doc_id":"doc-2","title":"Milvus Hinweis","text":"Milvus speichert Embeddings für semantische Suche."}
    ],
    "relations": [
      {"source_id":"doc-1","target_id":"doc-2","relation":"RELATED_TO"}
    ]
  }'
```

### 5.2 Chat testen (liest aus Milvus, nutzt LLM)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Wofür wird Milvus in diesem Stack genutzt?"}'
```

Wenn du eine Antwort mit Quellen erhältst, funktioniert die Retrieval-Kette.

### 5.3 Neo4j visuell prüfen

- Browser öffnen: `http://localhost:7474`
- Login: `neo4j` / `password`
- Beispiel-Query:

```cypher
MATCH (d:Document)
RETURN d
LIMIT 25;
```

### 5.4 Milvus im Browser prüfen (Attu)

Milvus selbst hat kein eingebautes Browser-UI wie Neo4j. Für eine visuelle Kontrolle kannst du **Attu** (offizielles Milvus-UI) nutzen.

Attu starten:

```bash
docker run -d --name attu --network docker_default -p 3001:3000 zilliz/attu:v2.4
```

Dann im Browser öffnen: `http://localhost:3001`

Verbindung in Attu anlegen:
- **Address:** `milvus-standalone`
- **Port:** `19530`
- **Username/Password:** leer lassen (für diese lokale Compose-Konfiguration)

Danach solltest du die Collection aus `MILVUS_COLLECTION` (Standard: `documents`) sehen und Einträge nach dem Ingest prüfen können.

> Hinweis: Wenn Attu außerhalb des Compose-Netzwerks läuft, nutze statt `milvus-standalone` die Adresse `host.docker.internal` (oder `localhost`, je nach Setup).

## 6) Fehlerbehebung

- **Connection refused zu Milvus (`localhost:19530`)**
  - Prüfe `docker compose ps` im `docker/`-Ordner.
  - Warte bei erstem Start etwas länger, bis Milvus vollständig bereit ist.

- **Neo4j Auth-Fehler**
  - `NEO4J_PASSWORD` in `.env` muss zu `NEO4J_AUTH` aus Compose passen.

- **Leere Retrieval-Ergebnisse**
  - Stelle sicher, dass `/ingest` erfolgreich war.
  - Prüfe, ob Embeddings mit passendem OpenAI-Key erzeugt werden konnten.

## 7) Produktion/Cloud (Kurzüberblick)

Für Deployment außerhalb lokalem Docker:
- Neo4j URI auf Managed-Instanz setzen (z. B. AuraDB).
- Milvus Host/Port auf Managed Milvus (z. B. Zilliz Cloud) setzen.
- Zugangsdaten als Secrets verwalten, nicht im Repo speichern.
- Netzwerkzugriff zwischen API, Neo4j und Milvus absichern.
