from __future__ import annotations

from app.mapper import retrieval_result_to_chat_response
from app.schemas import ChatRequest, ChatResponse

try:
    from fastapi import FastAPI
except ModuleNotFoundError:  # pragma: no cover - local test fallback if fastapi isn't installed.
    FastAPI = None


if FastAPI is not None:
    app = FastAPI()

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        retrieval_result = {
            "answer": f"Antwort auf: {request.query}",
            "sources": [],
            "entities": [],
            "graph_preview": {"nodes": [], "edges": []},
        }
        return retrieval_result_to_chat_response(retrieval_result)
else:
    app = None

    def chat(request: ChatRequest) -> ChatResponse:
        retrieval_result = {
            "answer": f"Antwort auf: {request.query}",
            "sources": [],
            "entities": [],
            "graph_preview": {"nodes": [], "edges": []},
        }
        return retrieval_result_to_chat_response(retrieval_result)
