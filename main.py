from __future__ import annotations

import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from pydantic import BaseModel, Field, model_validator

from config import CHUNK_SIZE, MILVUS_URI, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from config import CHUNK_BULLET_LISTS_ENABLED, CHUNK_MIN_CHARS, CHUNK_PARAGRAPHS_ENABLED

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - optional in tests
    GraphDatabase = None

try:
    from pymilvus import MilvusClient
except Exception:  # pragma: no cover - optional in tests
    MilvusClient = None


@dataclass
class Document:
    id: str
    content: str
    source: str
    entities: list[dict[str, str]] = field(default_factory=list)


class IngestRequest(BaseModel):
    documents: List[str | dict[str, str]] = Field(
        default_factory=list,
        description="Documents to store as plain strings or objects with text/content",
    )
    entity_candidates: List[str] = Field(
        default_factory=lambda: ["person", "company"],
        description="Entity candidate types to extract during ingestion (person, company)",
    )


class IngestResponse(BaseModel):
    ingested: int


class DocumentResponse(BaseModel):
    doc_id: str
    title: str
    file_name: str
    uploaded_at: datetime
    chunk_count: int


class DocumentUpdateRequest(BaseModel):
    title: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    query: str | None = None
    question: str | None = None
    top_k: int = 3
    graph_hops: int = 2
    use_graph: bool = True
    use_vector: bool = True
    return_debug: bool = True
    entity_candidates: List[str] = Field(default_factory=lambda: ["person", "company"])

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
DOCUMENT_STORE: dict[str, DocumentResponse] = {}
CHUNK_STORE: dict[str, dict[str, str]] = {}
UPLOAD_DIR = Path("/data/uploads")
DOCUMENT_METADATA: dict[str, dict[str, str]] = {}

GRAPH_PREVIEW_DEFAULT_NODE_LIMIT = 50
GRAPH_PREVIEW_DEFAULT_EDGE_LIMIT = 100
GRAPH_DOCUMENT_MAX_NODES = 200
GRAPH_DOCUMENT_MAX_EDGES = 400

_BULLET_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_PERSON_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")
_COMPANY_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z&.-]*(?:\s+[A-Z][A-Za-z&.-]*)*\s+(?:Inc|LLC|Ltd|GmbH|AG|Corp|Corporation|Company))\b"
)


def _is_list_block(block: str) -> bool:
    lines = [line for line in (part.strip() for part in block.splitlines()) if line]
    return bool(lines) and all(_BULLET_PATTERN.match(line) for line in lines)


def _split_text_by_size(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    words = text.split()
    current_words: list[str] = []
    current_length = 0
    for word in words:
        projected_length = current_length + len(word) + (1 if current_words else 0)
        if current_words and projected_length > CHUNK_SIZE:
            chunks.append(" ".join(current_words))
            current_words = [word]
            current_length = len(word)
            continue

        current_words.append(word)
        current_length = projected_length

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def _merge_short_chunks(chunks: list[str]) -> list[str]:
    min_chars = max(CHUNK_MIN_CHARS, 1)
    if min_chars <= 1:
        return chunks

    merged: list[str] = []
    pending = ""
    for chunk in chunks:
        if len(chunk) < min_chars:
            pending = f"{pending}\n\n{chunk}".strip() if pending else chunk
            continue

        if pending:
            combined = f"{pending}\n\n{chunk}".strip()
            if len(combined) <= CHUNK_SIZE:
                merged.append(combined)
                pending = ""
                continue
            merged.extend(_split_text_by_size(pending))
            pending = ""

        merged.append(chunk)

    if pending:
        if merged:
            combined = f"{merged[-1]}\n\n{pending}".strip()
            if len(combined) <= CHUNK_SIZE:
                merged[-1] = combined
            else:
                merged.extend(_split_text_by_size(pending))
        else:
            merged.extend(_split_text_by_size(pending))

    return merged


def _chunk_text(text: str) -> list[str]:
    raw_blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not raw_blocks:
        raw_blocks = [text.strip()]

    chunks: list[str] = []
    fallback_blocks: list[str] = []
    for block in raw_blocks:
        is_list = _is_list_block(block)
        should_chunk_block = CHUNK_BULLET_LISTS_ENABLED if is_list else CHUNK_PARAGRAPHS_ENABLED
        if should_chunk_block:
            if fallback_blocks:
                chunks.extend(_split_text_by_size("\n\n".join(fallback_blocks)))
                fallback_blocks = []
            chunks.extend(_split_text_by_size(block))
        else:
            fallback_blocks.append(block)

    if fallback_blocks:
        chunks.extend(_split_text_by_size("\n\n".join(fallback_blocks)))

    return _merge_short_chunks(chunks)


def _normalize_entity_candidates(candidates: list[str] | None) -> set[str]:
    if not candidates:
        return {"person", "company"}
    normalized = {candidate.strip().lower() for candidate in candidates if candidate.strip()}
    return normalized or {"person", "company"}


def _extract_entities(text: str, candidates: list[str] | None = None) -> list[dict[str, str]]:
    requested = _normalize_entity_candidates(candidates)
    entities: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    if "company" in requested:
        for match in _COMPANY_PATTERN.findall(text):
            key = match.strip()
            dedupe_key = ("company", key.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            entities.append({"key": f"company:{key.lower()}", "name": key, "type": "company"})

    if "person" in requested:
        for match in _PERSON_PATTERN.findall(text):
            name = match.strip()
            if _COMPANY_PATTERN.search(name):
                continue
            dedupe_key = ("person", name.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            entities.append({"key": f"person:{name.lower()}", "name": name, "type": "person"})

    return entities


def _persist_document_neo4j(document: DocumentResponse, chunks: list[tuple[str, str]]) -> None:
    if not (GraphDatabase and NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        session.run(
            """
            MERGE (d:Document {doc_id: $doc_id})
            SET d.title = $title,
                d.file_name = $file_name,
                d.uploaded_at = datetime($uploaded_at),
                d.chunk_count = $chunk_count
            """,
            doc_id=document.doc_id,
            title=document.title,
            file_name=document.file_name,
            uploaded_at=document.uploaded_at.isoformat(),
            chunk_count=document.chunk_count,
        )

        for chunk_id, chunk_text in chunks:
            session.run(
                """
                MATCH (d:Document {doc_id: $doc_id})
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.doc_id = $doc_id, c.text = $text
                MERGE (d)-[:HAS_CHUNK]->(c)
                """,
                doc_id=document.doc_id,
                chunk_id=chunk_id,
                text=chunk_text,
            )
    driver.close()


def _delete_document_neo4j(doc_id: str) -> None:
    if not (GraphDatabase and NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        session.run(
            """
            MATCH (d:Document {doc_id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE c
            """,
            doc_id=doc_id,
        )
        session.run("MATCH (d:Document {doc_id: $doc_id}) DETACH DELETE d", doc_id=doc_id)
    driver.close()


def _delete_embeddings_milvus(doc_id: str) -> None:
    if not (MilvusClient and MILVUS_URI):
        return

    client = MilvusClient(uri=MILVUS_URI)
    try:
        client.delete(collection_name="chunks", filter=f'doc_id == "{doc_id}"')
    except Exception:
        return


def retrieval(question: str, k: int = 3, entity_candidates: list[str] | None = None) -> List[Document]:
    """Return the top-k most relevant docs using a simple token overlap score."""
    question_terms = set(question.lower().split())
    scored: List[tuple[int, Document]] = []

    query_entities = {
        entity["key"] for entity in _extract_entities(question, candidates=entity_candidates)
    }

    for doc in VECTOR_STORE:
        doc_terms = set(doc.content.lower().split())
        lexical_score = len(question_terms & doc_terms)
        doc_entity_keys = {entity["key"] for entity in doc.entities}
        entity_score = len(query_entities & doc_entity_keys) * 3
        score = lexical_score + entity_score
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


def fetch_document_graph_preview(
    doc_id: str,
    max_nodes: int = GRAPH_DOCUMENT_MAX_NODES,
    max_edges: int = GRAPH_DOCUMENT_MAX_EDGES,
) -> GraphPreviewItem:
    if not NEO4J_URI or not NEO4J_USER or not NEO4J_PASSWORD:
        return _build_document_graph_preview_from_vector_store(
            doc_id=doc_id,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )

    if doc_id == "all":
        query = """
    MATCH (d:Document)-[:HAS_CHUNK]->(c)-[:MENTIONS]->(e)
    OPTIONAL MATCH (e)-[r]->(e2)
    RETURN
      collect(DISTINCT e) AS entities,
      collect(DISTINCT e2) AS neighbors,
      collect(DISTINCT {
        source: toString(id(e)),
        target: toString(id(e2)),
        label: type(r)
      }) AS raw_edges
    """
        query_params: dict[str, str] = {}
    else:
        query = """
    MATCH (d:Document {doc_id:$doc_id})-[:HAS_CHUNK]->(c)-[:MENTIONS]->(e)
    OPTIONAL MATCH (e)-[r]->(e2)
    RETURN
      collect(DISTINCT e) AS entities,
      collect(DISTINCT e2) AS neighbors,
      collect(DISTINCT {
        source: toString(id(e)),
        target: toString(id(e2)),
        label: type(r)
      }) AS raw_edges
    """
        query_params = {"doc_id": doc_id}

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            record = session.run(query, **query_params).single()

    if record is None:
        return GraphPreviewItem()

    entities = record["entities"] or []
    neighbors = record["neighbors"] or []
    raw_edges = record["raw_edges"] or []

    nodes: list[GraphNodeItem] = []
    node_ids: set[str] = set()
    for node in [*entities, *neighbors]:
        if node is None:
            continue
        node_id = str(node.id)
        if node_id in node_ids:
            continue
        node_ids.add(node_id)

        labels = list(node.labels)
        node_type = labels[0].lower() if labels else "entity"
        nodes.append(
            GraphNodeItem(
                id=node_id,
                label=node.get("name") or node.get("label") or node.get("doc_id") or node_id,
                type=node_type,
            )
        )
        if len(nodes) >= max_nodes:
            break

    allowed_node_ids = {node.id for node in nodes}
    edges: list[GraphEdgeItem] = []
    for edge in raw_edges:
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        if source not in allowed_node_ids or target not in allowed_node_ids:
            continue
        edges.append(GraphEdgeItem(source=source, target=target, label=edge.get("label") or "related_to"))
        if len(edges) >= max_edges:
            break

    return GraphPreviewItem(nodes=nodes, edges=edges)


def _build_document_graph_preview_from_vector_store(
    doc_id: str,
    max_nodes: int,
    max_edges: int,
) -> GraphPreviewItem:
    bounded_max_nodes = max(0, max_nodes)
    bounded_max_edges = max(0, max_edges)

    relevant_docs = VECTOR_STORE if doc_id == "all" else [item for item in VECTOR_STORE if item.source == doc_id]

    entity_keys: list[str] = []
    seen_entity_keys: set[str] = set()

    for document in relevant_docs:
        for entity in document.entities:
            key = str(entity.get("key", "")).strip()
            if not key or key in seen_entity_keys:
                continue
            seen_entity_keys.add(key)
            entity_keys.append(key)

    if not entity_keys and doc_id != "all":
        fallback_doc_chunks = [chunk_id for chunk_id, chunk in CHUNK_STORE.items() if chunk["doc_id"] == doc_id]
        entity_keys.extend(fallback_doc_chunks)

    preview = build_graph_preview(entity_keys, max_nodes=bounded_max_nodes, max_edges=bounded_max_edges)
    return GraphPreviewItem(**preview)


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
    entity_candidates = ["person", "company"]
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        payload = IngestRequest.model_validate(body)
        entity_candidates = payload.entity_candidates
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
        VECTOR_STORE.append(
            Document(
                id=str(i),
                content=content,
                source=f"doc-{i}",
                entities=_extract_entities(content, candidates=entity_candidates),
            )
        )

    return IngestResponse(ingested=len(documents))


@app.get("/documents", response_model=list[DocumentResponse])
def list_documents() -> list[DocumentResponse]:
    return sorted(DOCUMENT_STORE.values(), key=lambda item: item.uploaded_at, reverse=True)


@app.get("/documents/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: str) -> DocumentResponse:
    document = DOCUMENT_STORE.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(request: Request) -> DocumentResponse:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=415, detail="Unsupported content type")

    files = _parse_multipart_files(await request.body(), content_type)
    if not files:
        raise HTTPException(status_code=400, detail="No file provided")

    file_name, raw_content = files[0]
    try:
        text = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text") from exc

    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    doc_id = str(uuid4())
    upload_time = datetime.now(tz=timezone.utc)
    chunks = _chunk_text(text)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_file_name = Path(file_name).name
    file_path = UPLOAD_DIR / f"{doc_id}_{safe_file_name}"
    file_path.write_bytes(raw_content)

    document = DocumentResponse(
        doc_id=doc_id,
        title=Path(safe_file_name).stem,
        file_name=safe_file_name,
        uploaded_at=upload_time,
        chunk_count=len(chunks),
    )
    DOCUMENT_STORE[doc_id] = document
    DOCUMENT_METADATA[doc_id] = {}

    chunk_pairs: list[tuple[str, str]] = []
    for chunk_text in chunks:
        chunk_id = str(uuid4())
        chunk_pairs.append((chunk_id, chunk_text))
        CHUNK_STORE[chunk_id] = {"doc_id": doc_id, "text": chunk_text}
        VECTOR_STORE.append(
            Document(
                id=chunk_id,
                content=chunk_text,
                source=doc_id,
                entities=_extract_entities(chunk_text),
            )
        )

    _persist_document_neo4j(document, chunk_pairs)

    return document


@app.put("/documents/{doc_id}", response_model=DocumentResponse)
def update_document(doc_id: str, payload: DocumentUpdateRequest) -> DocumentResponse:
    document = DOCUMENT_STORE.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    new_title = payload.title.strip() if payload.title else document.title
    updated_document = document.model_copy(update={"title": new_title})
    DOCUMENT_STORE[doc_id] = updated_document
    DOCUMENT_METADATA[doc_id] = payload.metadata
    return updated_document


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str) -> dict[str, str]:
    document = DOCUMENT_STORE.pop(doc_id, None)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_ids = [chunk_id for chunk_id, chunk in CHUNK_STORE.items() if chunk["doc_id"] == doc_id]
    for chunk_id in chunk_ids:
        CHUNK_STORE.pop(chunk_id, None)

    VECTOR_STORE[:] = [item for item in VECTOR_STORE if item.source != doc_id]
    DOCUMENT_METADATA.pop(doc_id, None)

    _delete_document_neo4j(doc_id)
    _delete_embeddings_milvus(doc_id)

    for candidate in UPLOAD_DIR.glob(f"{doc_id}_*"):
        if candidate.is_file():
            candidate.unlink()

    return {"status": "deleted", "doc_id": doc_id}


@app.post("/documents/{doc_id}/reindex")
def reindex_document(doc_id: str) -> dict[str, object]:
    document = DOCUMENT_STORE.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    upload_file = next((candidate for candidate in UPLOAD_DIR.glob(f"{doc_id}_*") if candidate.is_file()), None)
    if upload_file is None:
        raise HTTPException(status_code=404, detail="Uploaded file for document not found")

    raw_content = upload_file.read_bytes()
    try:
        text = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text") from exc

    chunks = _chunk_text(text)

    old_chunk_ids = [chunk_id for chunk_id, chunk in CHUNK_STORE.items() if chunk["doc_id"] == doc_id]
    for chunk_id in old_chunk_ids:
        CHUNK_STORE.pop(chunk_id, None)

    VECTOR_STORE[:] = [item for item in VECTOR_STORE if item.source != doc_id]

    chunk_pairs: list[tuple[str, str]] = []
    for chunk_text in chunks:
        chunk_id = str(uuid4())
        chunk_pairs.append((chunk_id, chunk_text))
        CHUNK_STORE[chunk_id] = {"doc_id": doc_id, "text": chunk_text}
        VECTOR_STORE.append(
            Document(
                id=chunk_id,
                content=chunk_text,
                source=doc_id,
                entities=_extract_entities(chunk_text),
            )
        )

    updated_document = document.model_copy(update={"chunk_count": len(chunks)})
    DOCUMENT_STORE[doc_id] = updated_document

    _delete_document_neo4j(doc_id)
    _persist_document_neo4j(updated_document, chunk_pairs)
    _delete_embeddings_milvus(doc_id)

    return {"reindexed": True, "doc_id": doc_id, "chunk_count": len(chunks)}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    question = payload.query or payload.question or ""
    docs = retrieval(question, k=payload.top_k, entity_candidates=payload.entity_candidates)
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

    response_entities: list[EntityItem] = []
    seen_entity_keys: set[str] = set()
    for doc in docs:
        for entity in doc.entities:
            if entity["key"] in seen_entity_keys:
                continue
            seen_entity_keys.add(entity["key"])
            response_entities.append(
                EntityItem(
                    key=entity["key"],
                    name=entity["name"],
                    type=entity["type"],
                    salience=1.0,
                    source_chunk_ids=[doc.id],
                )
            )

    return ChatResponse(
        answer=answer,
        citations=citations,
        sources=sources,
        entities=response_entities,
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


@app.get("/graph/document/{doc_id}", response_model=GraphPreviewItem)
def graph_document(doc_id: str) -> GraphPreviewItem:
    return fetch_document_graph_preview(
        doc_id=doc_id,
        max_nodes=GRAPH_DOCUMENT_MAX_NODES,
        max_edges=GRAPH_DOCUMENT_MAX_EDGES,
    )


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
