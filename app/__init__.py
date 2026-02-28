from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="GraphRAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DocumentIn(BaseModel):
    id: str | None = None
    title: str | None = None
    text: str


class IngestRequest(BaseModel):
    documents: list[str | DocumentIn]


def build_preview(entity_keys: list[str]) -> dict:
    nodes = [{"id": key, "label": key, "type": "entity"} for key in entity_keys]
    edges = [
        {
            "source": entity_keys[idx],
            "target": entity_keys[idx + 1],
            "label": "related_to",
        }
        for idx in range(len(entity_keys) - 1)
    ]
    return {"nodes": nodes, "edges": edges}


@app.get("/graph/preview")
def graph_preview(entity_keys: str = Query(default="")) -> dict:
    keys = [key.strip() for key in entity_keys.split(",") if key.strip()]
    return build_preview(keys)


@app.post("/ingest")
def ingest(payload: IngestRequest) -> dict[str, Any]:
    normalized_docs = []

    for index, doc in enumerate(payload.documents, start=1):
        if isinstance(doc, str):
            normalized_docs.append({"id": f"doc-{index}", "text": doc})
            continue

        normalized_docs.append(doc.model_dump())

    from app.ingest import ingest_documents

    return ingest_documents(normalized_docs)
