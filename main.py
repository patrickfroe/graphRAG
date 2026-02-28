from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


@dataclass
class Document:
    id: str
    content: str
    source: str


class IngestRequest(BaseModel):
    documents: List[str] = Field(default_factory=list, description="Documents to store")


class IngestResponse(BaseModel):
    ingested: int


class ChatRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    id: str
    source: str
    content: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceItem]


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
        documents.extend(payload.documents)

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
    docs = retrieval(payload.question)
    answer = generate_answer(payload.question, docs)
    sources = [SourceItem(id=d.id, source=d.source, content=d.content) for d in docs]
    return ChatResponse(answer=answer, sources=sources)
