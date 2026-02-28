from __future__ import annotations

from app.mapper import retrieval_result_to_chat_response
from app.schemas import ChatRequest, ChatResponse

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError:  # pragma: no cover - local test fallback if fastapi isn't installed.
    FastAPI = None
    CORSMiddleware = None


def _chat_impl(request: ChatRequest) -> ChatResponse:
    retrieval_result = {
        "answer": f"Antwort auf: {request.query}",
        "sources": [],
        "entities": [],
        "graph_preview": {"nodes": [], "edges": []},
    }
    return retrieval_result_to_chat_response(retrieval_result)


if FastAPI is not None:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        return _chat_impl(request)
else:
    app = None

    def chat(request: ChatRequest) -> ChatResponse:
        return _chat_impl(request)
