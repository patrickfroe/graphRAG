"""Chat service primitives for full and streaming responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass
class ChatService:
    """A tiny deterministic chat service with token streaming support."""

    system_prompt: str = (
        "You are a graph-RAG assistant. Ground answers in retrieved graph context "
        "and be explicit when context is missing."
    )

    def generate_reply(self, message: str) -> str:
        """Return a full response for a user message."""
        normalized = " ".join(message.strip().split())
        if not normalized:
            return "Please provide a message so I can help."

        return (
            "Based on available graph context, here's a concise answer to: "
            f"'{normalized}'. If graph evidence is incomplete, I can refine after more retrieval."
        )

    def stream_reply(self, message: str) -> Iterator[str]:
        """Yield a response incrementally as whitespace-delimited chunks."""
        reply = self.generate_reply(message)
        for token in reply.split(" "):
            yield token + " "
