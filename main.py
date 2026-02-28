from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator


@dataclass
class Document:
    id: str
    content: str
    source: str


class IngestRequest(BaseModel):
    documents: List[str | dict[str, str]] = Field(
        default_factory=list,
        description="Documents to store as plain strings or objects with text/content",
    )


class IngestResponse(BaseModel):
    ingested: int


class ChatRequest(BaseModel):
    query: str | None = None
    question: str | None = None
    top_k: int = 3
    graph_hops: int = 2
    use_graph: bool = True
    use_vector: bool = True
    return_debug: bool = True

    @model_validator(mode="after")
    def ensure_query_present(self) -> "ChatRequest":
        effective_query = (self.query or self.question or "").strip()
        if not effective_query:
            raise ValueError("Either 'query' or 'question' is required")

        self.query = effective_query
        return self


class CitationItem(BaseModel):
    marker: str
    chunk_id: str
    doc_id: str
    score: float


class SourceItem(BaseModel):
    source_id: str
    doc_id: str
    chunk_id: str
    score: float
    title: str | None = None
    snippet: str
    text: str | None = None


class EntityItem(BaseModel):
    key: str
    name: str
    type: str
    salience: float
    source_chunk_ids: List[str] = Field(default_factory=list)


class GraphNodeItem(BaseModel):
    id: str
    label: str
    type: str = "entity"


class GraphEdgeItem(BaseModel):
    source: str
    target: str
    label: str = "related_to"


class GraphPreviewItem(BaseModel):
    nodes: List[GraphNodeItem] = Field(default_factory=list)
    edges: List[GraphEdgeItem] = Field(default_factory=list)


class GraphEvidenceItem(BaseModel):
    seed_entity_keys: List[str] = Field(default_factory=list)
    preview: GraphPreviewItem = Field(default_factory=GraphPreviewItem)


class ChatResponse(BaseModel):
    answer: str
    citations: List[CitationItem] = Field(default_factory=list)
    sources: List[SourceItem] = Field(default_factory=list)
    entities: List[EntityItem] = Field(default_factory=list)
    graph_evidence: GraphEvidenceItem = Field(default_factory=GraphEvidenceItem)


app = FastAPI(title="graphRAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for demo purposes
VECTOR_STORE: List[Document] = []

GRAPH_PREVIEW_DEFAULT_NODE_LIMIT = 50
GRAPH_PREVIEW_DEFAULT_EDGE_LIMIT = 100


def retrieval(question: str, k: int = 3) -> List[Document]:
    """Return the top-k most relevant docs using a simple token overlap score."""
    question_terms = set(question.lower().split())
    scored: List[tuple[int, Document]] = []

    for doc in VECTOR_STORE:
        doc_terms = set(doc.content.lower().split())
        score = len(question_terms & doc_terms)
        scored.append((score, doc))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc for score, doc in scored if score > 0][:k]


def generate_answer(question: str, docs: List[Document]) -> str:
    """Generate an answer from retrieved context."""
    if not docs:
        return (
            "I could not find relevant context in the indexed documents. "
            "Try ingesting more related content."
        )

    context = "\n".join(f"- {doc.content}" for doc in docs)
    return f"Question: {question}\n\nBased on retrieved context:\n{context}"


def build_graph_preview(
    entity_keys: list[str],
    max_nodes: int = GRAPH_PREVIEW_DEFAULT_NODE_LIMIT,
    max_edges: int = GRAPH_PREVIEW_DEFAULT_EDGE_LIMIT,
) -> dict[str, list[dict[str, str]]]:
    bounded_max_nodes = max(0, max_nodes)
    bounded_max_edges = max(0, max_edges)

    capped_keys = entity_keys[:bounded_max_nodes]
    nodes = [{"id": key, "label": key, "type": "entity"} for key in capped_keys]

    edges = [
        {
            "source": capped_keys[index],
            "target": capped_keys[index + 1],
            "label": "related_to",
        }
        for index in range(len(capped_keys) - 1)
    ][:bounded_max_edges]

    return {"nodes": nodes, "edges": edges}


def _parse_multipart_files(body: bytes, content_type: str) -> list[tuple[str, bytes]]:
    boundary_match = re.search(r'boundary="?([^";]+)"?', content_type)
    if not boundary_match:
        raise HTTPException(status_code=400, detail="Missing multipart boundary")

    boundary = boundary_match.group(1).encode("utf-8")
    delimiter = b"--" + boundary
    parts = body.split(delimiter)
    files: list[tuple[str, bytes]] = []

    for part in parts:
        chunk = part.strip()
        if not chunk or chunk == b"--":
            continue

        if chunk.endswith(b"--"):
            chunk = chunk[:-2].strip()

        headers, separator, payload = chunk.partition(b"\r\n\r\n")
        if not separator:
            continue

        content_disposition = ""
        for header_line in headers.decode("utf-8", errors="ignore").split("\r\n"):
            if header_line.lower().startswith("content-disposition:"):
                content_disposition = header_line
                break

        filename_match = re.search(r'filename="([^"]*)"', content_disposition)
        if not filename_match:
            continue

        filename = filename_match.group(1)
        files.append((filename, payload.rstrip(b"\r\n")))

    return files


@app.post("/ingest", response_model=IngestResponse)
async def ingest(request: Request) -> IngestResponse:
    documents: List[str] = []
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        payload = IngestRequest.model_validate(body)
        for item in payload.documents:
            if isinstance(item, str):
                text = item.strip()
            else:
                text = (item.get("text") or item.get("content") or "").strip()

            if text:
                documents.append(text)

    elif "multipart/form-data" in content_type:
        uploaded_files = _parse_multipart_files(await request.body(), content_type)
        allowed_extensions = {".txt", ".md", ".csv", ".json"}

        for filename, raw_content in uploaded_files:
            if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type '{filename}'. Allowed: .txt, .md, .csv, .json",
                )

            try:
                decoded = raw_content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"File '{filename}' must be UTF-8 encoded text",
                ) from exc

            stripped = decoded.strip()
            if stripped:
                documents.append(stripped)

    else:
        raise HTTPException(status_code=415, detail="Unsupported content type")

    if not documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    for i, content in enumerate(documents, start=len(VECTOR_STORE) + 1):
        VECTOR_STORE.append(Document(id=str(i), content=content, source=f"doc-{i}"))

    return IngestResponse(ingested=len(documents))


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    question = payload.query or payload.question or ""
    docs = retrieval(question, k=payload.top_k)
    answer = generate_answer(question, docs)

    sources = [
        SourceItem(
            source_id=f"S{index}",
            doc_id=d.source,
            chunk_id=d.id,
            score=1.0,
            title=d.source,
            snippet=d.content,
            text=d.content,
        )
        for index, d in enumerate(docs, start=1)
    ]
    citations = [
        CitationItem(marker=f"[{source.source_id}]", chunk_id=source.chunk_id, doc_id=source.doc_id, score=source.score)
        for source in sources
    ]

    seed_entity_keys = [source.doc_id for source in sources]
    preview_data = build_graph_preview(seed_entity_keys)

    return ChatResponse(
        answer=answer,
        citations=citations,
        sources=sources,
        entities=[],
        graph_evidence=GraphEvidenceItem(
            seed_entity_keys=seed_entity_keys,
            preview=GraphPreviewItem(**preview_data),
        ),
    )


@app.get("/graph/preview")
def graph_preview(
    entity_keys: str = "",
    max_nodes: int = GRAPH_PREVIEW_DEFAULT_NODE_LIMIT,
    max_edges: int = GRAPH_PREVIEW_DEFAULT_EDGE_LIMIT,
) -> dict[str, list[dict[str, str]]]:
    keys = [key.strip() for key in entity_keys.split(",") if key.strip()]
    return build_graph_preview(keys, max_nodes=max_nodes, max_edges=max_edges)


@app.get("/evidence")
def evidence(chunk_ids: str = "") -> dict[str, list[dict[str, str]]]:
    requested_chunk_ids = {chunk_id.strip() for chunk_id in chunk_ids.split(",") if chunk_id.strip()}

    if requested_chunk_ids:
        matched_documents = [document for document in VECTOR_STORE if document.id in requested_chunk_ids]
    else:
        matched_documents = []

    return {
        "chunks": [
            {
                "chunk_id": document.id,
                "doc_id": document.source,
                "title": document.source,
                "text": document.content,
            }
            for document in matched_documents
        ]
    }
