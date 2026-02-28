from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass
class Source:
    source_id: str
    snippet: str
    doc_id: str | None
    chunk_id: str | None
    score: float


@dataclass
class Entity:
    key: str
    salience: float
    frequency: int
    avg_score: float


@dataclass
class GraphNode:
    id: str
    label: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    type: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphPreview:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


@dataclass
class Trace:
    top_k: int | None
    hops: int | None
    graph_nodes: int
    graph_edges: int
    context_tokens_est: int


@dataclass
class ChatResponse:
    answer: str
    sources: list[Source]
    entities: list[Entity]
    graph_preview: GraphPreview
    trace: Trace


def _get(result: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in result:
            return result[key]
    return default


def _normalize_entities(entities: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not entities:
        return normalized

    if isinstance(entities, dict):
        entities = [entities]

    for entity in entities:
        if isinstance(entity, str):
            normalized.append({"key": entity})
        elif isinstance(entity, dict):
            key = entity.get("key") or entity.get("name") or entity.get("id")
            if key:
                normalized.append({**entity, "key": str(key)})
    return normalized


def _extract_graph(result: dict[str, Any]) -> GraphPreview:
    graph_raw = _get(result, "graph", "graph_result", "neo4j_result", default={}) or {}
    node_limit = 120
    edge_limit = 200

    nodes_raw = graph_raw.get("nodes", [])
    edges_raw = graph_raw.get("edges", [])

    nodes: list[GraphNode] = []
    known_node_ids: set[str] = set()
    for node in nodes_raw:
        node_id = str(node.get("id") or node.get("node_id") or node.get("elementId") or "")
        if not node_id or node_id in known_node_ids:
            continue
        known_node_ids.add(node_id)
        nodes.append(
            GraphNode(
                id=node_id,
                label=node.get("label") or node.get("name"),
                properties=node.get("properties") or {},
            )
        )
        if len(nodes) >= node_limit:
            break

    edges: list[GraphEdge] = []
    for edge in edges_raw:
        source = str(edge.get("source") or edge.get("start") or edge.get("from") or "")
        target = str(edge.get("target") or edge.get("end") or edge.get("to") or "")
        if not source or not target:
            continue
        if source not in known_node_ids or target not in known_node_ids:
            continue
        edges.append(
            GraphEdge(
                source=source,
                target=target,
                type=edge.get("type") or edge.get("label"),
                properties=edge.get("properties") or {},
            )
        )
        if len(edges) >= edge_limit:
            break

    return GraphPreview(nodes=nodes, edges=edges)


def _insert_citations(answer: str, sources: list[Source]) -> str:
    if not answer or not sources:
        return answer

    updated = answer
    for source in sources:
        marker = f"[{source.source_id}]"
        candidate_terms = [str(source.chunk_id or ""), str(source.doc_id or "")]

        for term in candidate_terms:
            if not term:
                continue
            if re.search(rf"\b{re.escape(term)}\b", updated) and marker not in updated:
                updated = re.sub(rf"\b{re.escape(term)}\b", f"{term} {marker}", updated, count=1)
                break

    if all(f"[{src.source_id}]" in updated for src in sources):
        return updated

    if not re.search(r"\[S\d+\]", updated):
        tail_markers = " ".join(f"[{src.source_id}]" for src in sources)
        updated = f"{updated.rstrip()} {tail_markers}".strip()

    return updated


def _estimate_context_tokens(answer: str, chunks: list[dict[str, Any]]) -> int:
    context = " ".join(
        [answer] + [str(chunk.get("text") or chunk.get("snippet") or "") for chunk in chunks]
    )
    return max(1, len(context.split()))


def build_chat_response(result: dict[str, Any]) -> ChatResponse:
    chunks = _get(result, "retrieved_chunks", "chunks", default=[]) or []
    answer = str(_get(result, "answer", "response", default="") or "")

    sources: list[Source] = []
    for idx, chunk in enumerate(chunks, start=1):
        source_id = f"S{idx}"
        sources.append(
            Source(
                source_id=source_id,
                snippet=str(chunk.get("snippet") or chunk.get("text") or "")[:500],
                doc_id=(str(chunk.get("doc_id")) if chunk.get("doc_id") is not None else None),
                chunk_id=(str(chunk.get("chunk_id")) if chunk.get("chunk_id") is not None else None),
                score=float(chunk.get("score") or 0.0),
            )
        )

    answer = _insert_citations(answer=answer, sources=sources)

    entity_agg: dict[str, dict[str, float]] = {}
    for chunk in chunks:
        score = float(chunk.get("score") or 0.0)
        for entity in _normalize_entities(chunk.get("entities")):
            key = entity["key"].strip()
            if not key:
                continue
            bucket = entity_agg.setdefault(key.lower(), {"frequency": 0.0, "score_sum": 0.0, "display": key})
            bucket["frequency"] += 1
            bucket["score_sum"] += score

    entities: list[Entity] = []
    for bucket in entity_agg.values():
        frequency = int(bucket["frequency"])
        avg_score = (bucket["score_sum"] / frequency) if frequency else 0.0
        salience = frequency * avg_score
        entities.append(
            Entity(
                key=bucket["display"],
                salience=salience,
                frequency=frequency,
                avg_score=avg_score,
            )
        )
    entities.sort(key=lambda e: e.salience, reverse=True)

    graph_preview = _extract_graph(result)

    trace = Trace(
        top_k=int(_get(result, "top_k", default=len(chunks)) or len(chunks)),
        hops=_get(result, "hops", default=None),
        graph_nodes=len(graph_preview.nodes),
        graph_edges=len(graph_preview.edges),
        context_tokens_est=int(
            _get(result, "context_tokens_est", default=_estimate_context_tokens(answer, chunks))
        ),
    )

    return ChatResponse(
        answer=answer,
        sources=sources,
        entities=entities,
        graph_preview=graph_preview,
        trace=trace,
    )
