from __future__ import annotations

import asyncio
import json
import re
import string
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Iterable, Sequence

from openai import OpenAI
from rapidfuzz import fuzz

from app.config import get_settings
from app.graph import GraphStore

ALLOWED_GLiner_LABELS = [
    "person",
    "organization",
    "company",
    "product",
    "technology",
    "location",
    "project",
    "document",
]

ALLOWED_LLM_TYPES = {"PERSON", "ORGANIZATION", "COMPANY", "PRODUCT", "TECHNOLOGY", "PROJECT"}


@dataclass
class ExtractedEntity:
    text: str
    type: str
    confidence: float = 0.0
    chunk_ids: set[str] = field(default_factory=set)

    @property
    def canonical_name(self) -> str:
        return normalize_entity_name(self.text)


@dataclass
class ExtractedRelationship:
    source: str
    target: str
    type: str
    confidence: float = 0.0


@lru_cache(maxsize=1)
def _load_gliner_model() -> Any:
    from gliner import GLiNER

    return GLiNER.from_pretrained("numind/NuNerZero")


def normalize_entity_name(name: str) -> str:
    lowered = name.lower().strip()
    no_punct = lowered.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", no_punct).strip()


def extract_entities_gliner(
    text: str,
    labels: Sequence[str] | None = None,
    model: Any | None = None,
) -> list[dict[str, Any]]:
    if not text.strip():
        return []

    gliner_model = model or _load_gliner_model()
    target_labels = list(labels or ALLOWED_GLiner_LABELS)
    raw_entities = gliner_model.predict_entities(text, target_labels)

    entities: list[dict[str, Any]] = []
    for item in raw_entities:
        entity_text = str(item.get("text", "")).strip()
        entity_type = str(item.get("label", "")).strip().lower()
        if not entity_text or not entity_type:
            continue
        entities.append(
            {
                "text": entity_text,
                "type": entity_type,
                "confidence": float(item.get("score", 0.0) or 0.0),
            }
        )
    return entities


def extract_entities_llm(text: str, client: OpenAI | None = None) -> list[dict[str, Any]]:
    if not text.strip():
        return []

    settings = get_settings()
    llm_client = client or OpenAI(api_key=settings.openai_api_key)
    prompt = (
        "You are an expert knowledge graph extraction engine.\n\n"
        "TASK:\n"
        "Extract entities from the following text.\n\n"
        "Return ONLY JSON.\n\n"
        "Entity types allowed:\n"
        "PERSON\nORGANIZATION\nCOMPANY\nPRODUCT\nTECHNOLOGY\nPROJECT\n\n"
        "Rules:\n"
        "- Include companies\n"
        "- Include people\n"
        "- Include products\n"
        "- Normalize names\n"
        "- Remove duplicates\n\n"
        "Output JSON:\n"
        "{\n"
        ' "entities":[\n'
        '   {"name":"Microsoft","type":"COMPANY"},\n'
        '   {"name":"Satya Nadella","type":"PERSON"}\n'
        " ]\n"
        "}\n\n"
        f"Text:\n{text}"
    )

    response = llm_client.chat.completions.create(
        model=settings.openai_chat_model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": "You are an expert knowledge graph extraction engine."}, {"role": "user", "content": prompt}],
    )

    content = response.choices[0].message.content or "{}"
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return []

    entities: list[dict[str, Any]] = []
    for item in payload.get("entities", []):
        name = str(item.get("name", "")).strip()
        entity_type = str(item.get("type", "")).strip().upper()
        if not name or entity_type not in ALLOWED_LLM_TYPES:
            continue
        entities.append({"text": name, "type": entity_type.lower(), "confidence": 0.75})
    return entities


def merge_entities(
    entities_a: Sequence[dict[str, Any]],
    entities_b: Sequence[dict[str, Any]],
    fuzzy_threshold: float = 0.9,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []

    for candidate in [*entities_a, *entities_b]:
        text = str(candidate.get("text", "")).strip()
        if not text:
            continue
        candidate_norm = normalize_entity_name(text)
        best_idx = -1

        for idx, existing in enumerate(merged):
            existing_norm = normalize_entity_name(existing["text"])
            if candidate_norm == existing_norm:
                best_idx = idx
                break
            score = fuzz.ratio(candidate_norm, existing_norm) / 100.0
            if score >= fuzzy_threshold:
                best_idx = idx
                break

        if best_idx >= 0:
            existing = merged[best_idx]
            existing_conf = float(existing.get("confidence", 0.0))
            candidate_conf = float(candidate.get("confidence", 0.0) or 0.0)
            existing["confidence"] = max(existing_conf, candidate_conf)
            if candidate_conf > existing_conf or (candidate_conf == existing_conf and len(text) > len(existing["text"])):
                existing["text"] = text
                existing["type"] = str(candidate.get("type", existing.get("type", "organization"))).lower()
            continue

        merged.append(
            {
                "text": text,
                "type": str(candidate.get("type", "organization")).lower(),
                "confidence": float(candidate.get("confidence", 0.0) or 0.0),
            }
        )

    return merged


def rank_entities(entities: Sequence[ExtractedEntity], min_score: float = 0.3) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for entity in entities:
        frequency = len(entity.chunk_ids)
        score = frequency * 0.6 + entity.confidence * 0.4
        if score < min_score:
            continue
        ranked.append(
            {
                "name": entity.text,
                "type": entity.type,
                "canonical_name": entity.canonical_name,
                "score": score,
                "frequency": frequency,
                "confidence": entity.confidence,
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def evaluate_entities(predicted: Iterable[str], gold: Iterable[str]) -> dict[str, float]:
    predicted_set = {normalize_entity_name(item) for item in predicted}
    gold_set = {normalize_entity_name(item) for item in gold}
    true_positives = len(predicted_set & gold_set)

    precision = true_positives / len(predicted_set) if predicted_set else 0.0
    recall = true_positives / len(gold_set) if gold_set else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "entity_frequency": float(len(predicted_set)),
    }


def extract_relationships_llm(text: str, client: OpenAI | None = None) -> list[dict[str, Any]]:
    if not text.strip():
        return []

    settings = get_settings()
    llm_client = client or OpenAI(api_key=settings.openai_api_key)
    prompt = (
        "Extract only these relationship triples from the text and return JSON only.\n"
        "Allowed relations:\n"
        "PERSON -> WORKS_FOR -> COMPANY\n"
        "COMPANY -> PRODUCES -> PRODUCT\n"
        "Output format: {\"relationships\":[{\"source\":\"...\",\"type\":\"WORKS_FOR\",\"target\":\"...\"}]}\n"
        f"Text:\n{text}"
    )
    response = llm_client.chat.completions.create(
        model=settings.openai_chat_model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": "You extract knowledge-graph relations."}, {"role": "user", "content": prompt}],
    )

    try:
        payload = json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return []

    relationships: list[dict[str, Any]] = []
    for rel in payload.get("relationships", []):
        source = str(rel.get("source", "")).strip()
        target = str(rel.get("target", "")).strip()
        rel_type = str(rel.get("type", "")).strip().upper()
        if not source or not target or rel_type not in {"WORKS_FOR", "PRODUCES"}:
            continue
        relationships.append({"source": source, "target": target, "type": rel_type})
    return relationships


async def extract_entities_batch(
    chunks: Sequence[dict[str, Any]],
    gliner_extractor: Callable[[str], list[dict[str, Any]]] = extract_entities_gliner,
    llm_extractor: Callable[[str], list[dict[str, Any]]] = extract_entities_llm,
    relationship_extractor: Callable[[str], list[dict[str, Any]]] = extract_relationships_llm,
) -> dict[str, list[dict[str, Any]]]:
    async def process_chunk(chunk: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        text = str(chunk.get("text", ""))
        chunk_id = str(chunk.get("chunk_id", ""))

        gliner_entities, llm_entities, relationships = await asyncio.gather(
            asyncio.to_thread(gliner_extractor, text),
            asyncio.to_thread(llm_extractor, text),
            asyncio.to_thread(relationship_extractor, text),
        )

        merged = merge_entities(gliner_entities, llm_entities)
        for entity in merged:
            entity["chunk_id"] = chunk_id

        for relationship in relationships:
            relationship["chunk_id"] = chunk_id

        return merged, relationships

    processed = await asyncio.gather(*(process_chunk(chunk) for chunk in chunks))

    by_canonical: dict[str, ExtractedEntity] = {}
    all_relationships: list[dict[str, Any]] = []
    for entities, relationships in processed:
        all_relationships.extend(relationships)
        for entity in entities:
            canonical = normalize_entity_name(entity["text"])
            if canonical in by_canonical:
                existing = by_canonical[canonical]
                existing.confidence = max(existing.confidence, float(entity.get("confidence", 0.0) or 0.0))
                existing.chunk_ids.add(str(entity.get("chunk_id", "")))
            else:
                by_canonical[canonical] = ExtractedEntity(
                    text=str(entity["text"]),
                    type=str(entity.get("type", "organization")),
                    confidence=float(entity.get("confidence", 0.0) or 0.0),
                    chunk_ids={str(entity.get("chunk_id", ""))},
                )

    ranked = rank_entities(list(by_canonical.values()))
    return {"entities": ranked, "relationships": all_relationships}


def persist_extraction_results(
    doc_id: str,
    chunks: Sequence[dict[str, Any]],
    extraction_result: dict[str, list[dict[str, Any]]],
    graph_store: GraphStore | None = None,
) -> None:
    store = graph_store or GraphStore()
    close_after = graph_store is None
    entity_chunk_lookup: dict[str, set[str]] = {}

    try:
        store.ensure_constraints()
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id", "")).strip()
            text = str(chunk.get("text", ""))
            if chunk_id:
                store.upsert_chunk(chunk_id=chunk_id, doc_id=doc_id, text=text)

        for entity in extraction_result.get("entities", []):
            canonical_name = str(entity.get("canonical_name", "")).strip()
            if not canonical_name:
                continue

            store.upsert_entity(
                name=str(entity.get("name", canonical_name)),
                entity_type=str(entity.get("type", "organization")),
                canonical_name=canonical_name,
                score=float(entity.get("score", 0.0) or 0.0),
            )
            entity_chunk_lookup[canonical_name] = set()

        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id", "")).strip()
            text = str(chunk.get("text", ""))
            normalized_text = normalize_entity_name(text)

            for entity in extraction_result.get("entities", []):
                canonical_name = str(entity.get("canonical_name", "")).strip()
                if canonical_name and canonical_name in normalized_text and chunk_id:
                    store.link_chunk_mentions_entity(chunk_id=chunk_id, canonical_name=canonical_name)
                    entity_chunk_lookup.setdefault(canonical_name, set()).add(chunk_id)

        for rel in extraction_result.get("relationships", []):
            relation_type = str(rel.get("type", "")).upper()
            if relation_type not in {"WORKS_FOR", "PRODUCES"}:
                continue
            source_canonical = normalize_entity_name(str(rel.get("source", "")))
            target_canonical = normalize_entity_name(str(rel.get("target", "")))
            if source_canonical and target_canonical:
                store.link_entity_relation(source_canonical, target_canonical, relation_type)
    finally:
        if close_after:
            store.close()
