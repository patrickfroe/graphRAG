# graphRAG

A minimal chat service with **streaming responses**.

## What was added

- `POST /chat`: returns a full response in one JSON payload.
- `POST /chat/stream`: streams the same response token-by-token using Server-Sent Events (SSE).

## Run

```bash
python -m graphrag.server
```

Server starts at `http://127.0.0.1:8000`.

## Example

### Non-streaming

```bash
curl -s -X POST http://127.0.0.1:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"How does graph retrieval help?"}'
```

### Streaming

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H 'content-type: application/json' \
  -d '{"message":"How does graph retrieval help?"}'
```

