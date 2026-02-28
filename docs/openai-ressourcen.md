# Anleitung: OpenAI-Ressourcen für Embeddings + LLM hinzufügen

Diese Anleitung zeigt dir, wie du in diesem Projekt die OpenAI-Ressourcen für
- **Embeddings** (Vektorisierung)
- **LLM/Chat** (Antwortgenerierung)
konfigurierst und testest.

## 1) Voraussetzungen

- OpenAI-Account mit aktivierter Abrechnung
- Ein API-Key aus der OpenAI-Konsole
- Python-Dependencies installiert (`pip install -r requirements.txt`)

## 2) Relevante Umgebungsvariablen

Das Backend lädt die Konfiguration aus einer `.env`-Datei im Projektroot.

Lege im Root des Repos eine Datei `.env` an:

```env
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
```

### Bedeutung

- `OPENAI_API_KEY`: API-Key für OpenAI
- `OPENAI_EMBEDDING_MODEL`: Modell für Embeddings (z. B. `text-embedding-3-small` oder `text-embedding-3-large`)
- `OPENAI_CHAT_MODEL`: Chat-/LLM-Modell (z. B. `gpt-4o-mini`, `gpt-4.1-mini`)

## 3) Welche Komponenten diese Werte nutzen

- **Embedding-Service** nutzt `OPENAI_EMBEDDING_MODEL` und `OPENAI_API_KEY`.
- **LLM-Service** nutzt `OPENAI_CHAT_MODEL` und `OPENAI_API_KEY`.

Die Variablen werden zentral in `app/config.py` geladen und in den Services in `app/embeddings.py` und `app/llm.py` verwendet.

## 4) Backend starten

```bash
uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

## 5) Funktionstest (Embeddings + LLM)

### 5.1 Dokumente ingestieren (nutzt Embedding-Modell)

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"documents":[{"doc_id":"doc-1","text":"GraphRAG verbindet Retrieval und LLM."}]}'
```

### 5.2 Chat-Anfrage (nutzt Embeddings + Chat-Modell)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Wofür wird GraphRAG verwendet?"}'
```

Wenn beide Requests erfolgreich sind, sind Embedding- und LLM-Ressource korrekt eingebunden.

## 6) Typische Fehlerbilder

- **401/403 von OpenAI**: `OPENAI_API_KEY` prüfen.
- **Model not found**: Modellname in `OPENAI_EMBEDDING_MODEL` oder `OPENAI_CHAT_MODEL` ist falsch oder nicht freigeschaltet.
- **Leere/irrelevante Antworten**: Ingest erneut ausführen und sicherstellen, dass verwertbarer Kontext vorhanden ist.

## 7) Modellwechsel ohne Codeänderung

Du kannst Embedding- und Chat-Modell jederzeit in der `.env` tauschen und den Backend-Prozess neu starten.
