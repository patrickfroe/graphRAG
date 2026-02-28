from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.schemas import ChatResponse, Entity, GraphPreview, Source

GRAPH_PREVIEW_NODE_LIMIT = 10
GRAPH_PREVIEW_EDGE_LIMIT = 20


def _build_sources(raw_sources: list[dict[str, Any]]) -> list[Source]:
    sources: list[Source] = []
    for index, raw in enumerate(raw_sources, start=1):
        sources.append(
            Source(
                source_id=f"S{index}",
                title=raw.get("title"),
                url=raw.get("url"),
                score=raw.get("score"),
                snippet=raw.get("snippet") or raw.get("text"),
            )
        )
    return sources


def _inject_markers(answer: str, sources: list[Source]) -> str:
    marker_suffix = " ".join(f"[{source.source_id}]" for source in sources)
    if not marker_suffix:
        return answer

    # Keep output deterministic and ensure every source marker is present exactly once.
    existing = {f"[{source.source_id}]" for source in sources if f"[{source.source_id}]" in answer}
    missing = [f"[{source.source_id}]" for source in sources if f"[{source.source_id}]" not in existing]
    if not missing:
        return answer
    return f"{answer.rstrip()} {' '.join(missing)}".strip()


def _build_entities(raw_entities: list[dict[str, Any]]) -> list[Entity]:
    aggregated: dict[str, dict[str, float]] = defaultdict(lambda: {"frequency": 0.0, "score": 0.0})

    for raw in raw_entities:
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        frequency = int(raw.get("frequency", 1) or 1)
        score = float(raw.get("score", 0.0) or 0.0)

        aggregated[name]["frequency"] += frequency
        aggregated[name]["score"] += score

    entities: list[Entity] = []
    for name, values in aggregated.items():
        frequency = int(values["frequency"])
        score = float(values["score"])
        salience = round(frequency * score, 6)
        entities.append(Entity(name=name, frequency=frequency, score=score, salience=salience))

    entities.sort(key=lambda entity: entity.salience, reverse=True)
    return entities


def _build_graph_preview(raw_graph: dict[str, Any] | None) -> GraphPreview:
    if not raw_graph:
        return GraphPreview()
    nodes = list(raw_graph.get("nodes", []))[:GRAPH_PREVIEW_NODE_LIMIT]
    edges = list(raw_graph.get("edges", []))[:GRAPH_PREVIEW_EDGE_LIMIT]
    return GraphPreview(nodes=nodes, edges=edges)


def retrieval_result_to_chat_response(retrieval_result: dict[str, Any]) -> ChatResponse:
    raw_sources = list(retrieval_result.get("sources", []))
    sources = _build_sources(raw_sources)

    answer = str(retrieval_result.get("answer", ""))
    answer_with_markers = _inject_markers(answer, sources)

    entities = _build_entities(list(retrieval_result.get("entities", [])))
    graph_preview = _build_graph_preview(retrieval_result.get("graph_preview"))

    return ChatResponse(
        answer=answer_with_markers,
        sources=sources,
        entities=entities,
        graph_preview=graph_preview,
    )
