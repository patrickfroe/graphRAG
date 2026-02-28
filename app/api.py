from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.ingest import ingest_documents
from app.retrieval import answer_query

app = FastAPI(title="GraphRAG MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DocumentIn(BaseModel):
    id: str
    title: str | None = None
    text: str


class IngestRequest(BaseModel):
    documents: list[DocumentIn]


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(payload: IngestRequest) -> dict:
    docs = [doc.model_dump() for doc in payload.documents]
    return ingest_documents(docs)


@app.post("/query")
def query(payload: QueryRequest) -> dict:
    return answer_query(query=payload.query, top_k=payload.top_k)
