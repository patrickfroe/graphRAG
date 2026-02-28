# graphRAG

A minimal response contract for GraphRAG-style chat results.

## Chat response layout

Every chat response should contain these sections:

1. **Answer**: the natural-language response to the user.
2. **Sources**: citations or references used to produce the answer.
3. **Entities**: extracted named entities (people, orgs, systems, etc.).
4. **View Graph**: graph-oriented relationships connecting the entities.

## Markdown template

Use the template in `templates/chat_response.md` to keep output consistent.
# graphRAG FastAPI service

## Endpoints

- `POST /ingest`
  - Body: `{"documents": ["text 1", "text 2"]}`
  - Stores incoming documents in an in-memory index.

- `POST /chat`
  - Body: `{"question": "..."}`
  - Flow:
    1. `retrieval(question)`
    2. `generate_answer(question, docs)`
    3. Returns `answer` + `sources`

## Run

```bash
uvicorn main:app --reload
```
# GraphRAG Python MVP

Ein minimales GraphRAG-MVP mit:

- **FastAPI** für HTTP-Endpunkte
- **Neo4j** als Graph-Datenbank
- **Milvus** (PyMilvus) als Vektor-Datenbank
- **OpenAI API** für Embeddings + Chat

## Projektstruktur

```text
/app/api.py
/app/ingest.py
/app/retrieval.py
/app/graph.py
/app/vectorstore.py
/app/embeddings.py
/app/llm.py
/app/config.py
/docker/docker-compose.yml
requirements.txt
README.md
```

## Setup

1. Abhängigkeiten installieren:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. `.env` erstellen:

```env
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=documents

TOP_K=5
```

3. Neo4j + Milvus starten:

```bash
docker compose -f docker/docker-compose.yml up -d
```

4. API starten:

```bash
uvicorn app.api:app --reload --port 8000
```

## API-Endpunkte

### Health

```bash
curl http://localhost:8000/health
```

### Ingest

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {"id": "doc-1", "title": "GraphRAG", "text": "GraphRAG kombiniert Graphen und Vektorsuche."},
      {"id": "doc-2", "title": "Neo4j", "text": "Neo4j ist eine Graphdatenbank."}
    ]
  }'
```

### Query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Was ist GraphRAG?", "top_k": 3}'
```

## Hinweise

- Dieses Repo ist ein **MVP**. Für Produktion fehlen u. a.:
  - Authentifizierung
  - robustes Chunking / Parsing
  - Retry / Error-Handling
  - Monitoring / Tracing
  - Migrations & schema management
