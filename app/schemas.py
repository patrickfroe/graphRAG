from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatRequest:
    query: str


@dataclass
class Source:
    source_id: str
    title: str | None = None
    url: str | None = None
    score: float | None = None
    snippet: str | None = None


@dataclass
class Entity:
    name: str
    frequency: int = 1
    score: float = 0.0
    salience: float = 0.0


@dataclass
class GraphPreview:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ChatResponse:
    answer: str
    sources: list[Source] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    graph_preview: GraphPreview = field(default_factory=GraphPreview)
