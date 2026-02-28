from __future__ import annotations

from dataclasses import dataclass
from typing import List

from fastapi import FastAPI
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


@app.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest) -> IngestResponse:
    for i, content in enumerate(payload.documents, start=len(VECTOR_STORE) + 1):
        VECTOR_STORE.append(Document(id=str(i), content=content, source=f"doc-{i}"))

    return IngestResponse(ingested=len(payload.documents))


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    docs = retrieval(payload.question)
    answer = generate_answer(payload.question, docs)
    sources = [SourceItem(id=d.id, source=d.source, content=d.content) for d in docs]
    return ChatResponse(answer=answer, sources=sources)
