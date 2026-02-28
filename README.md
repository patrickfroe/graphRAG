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
