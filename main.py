from __future__ import annotations

import re
import json
import asyncio
import logging
import unicodedata
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
from pydantic import BaseModel, Field, model_validator

from config import CHUNK_SIZE, MILVUS_URI, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER, OPENAI_API_KEY, OPENAI_CHAT_MODEL
from config import CHUNK_BULLET_LISTS_ENABLED, CHUNK_MIN_CHARS, CHUNK_PARAGRAPHS_ENABLED
from openai import OpenAI

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover - optional in tests
    GraphDatabase = None

try:
    from pymilvus import MilvusClient
except Exception:  # pragma: no cover - optional in tests
    MilvusClient = None

try:
    from gliner import GLiNER
except Exception:  # pragma: no cover - optional in tests
    GLiNER = None

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - optional in tests
    fuzz = None


@dataclass
class Document:
    id: str
    content: str
    source: str
    entities: list[dict[str, str]] = field(default_factory=list)


class IngestRequest(BaseModel):
    documents: List[str | dict[str, str]] = Field(
        default_factory=list,
        description="Documents to store as plain strings or objects with text/content",
    )
    entity_candidates: List[str] = Field(
        default_factory=lambda: ["person", "company"],
        description="Entity candidate types to extract during ingestion (person, company)",
    )


class IngestResponse(BaseModel):
    ingested: int


class DocumentResponse(BaseModel):
    doc_id: str
    title: str
    file_name: str
    uploaded_at: datetime
    chunk_count: int
    extracted_entity_count: int = 0
    extracted_entities: list[dict[str, str | int]] = Field(default_factory=list)


class DocumentUpdateRequest(BaseModel):
    title: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    query: str | None = None
    question: str | None = None
    top_k: int = 3
    graph_hops: int = 2
    use_graph: bool = True
    use_vector: bool = True
    return_debug: bool = True
    entity_candidates: List[str] = Field(default_factory=lambda: ["person", "company"])

    @model_validator(mode="after")
    def ensure_query_present(self) -> "ChatRequest":
        effective_query = (self.query or self.question or "").strip()
        if not effective_query:
            raise ValueError("Either 'query' or 'question' is required")

        self.query = effective_query
        return self


class CitationItem(BaseModel):
    marker: str
    chunk_id: str
    doc_id: str
    score: float


class SourceItem(BaseModel):
    source_id: str
    doc_id: str
    chunk_id: str
    score: float
    title: str | None = None
    snippet: str
    text: str | None = None


class EntityItem(BaseModel):
    key: str
    name: str
    type: str
    salience: float
    source_chunk_ids: List[str] = Field(default_factory=list)


class GraphNodeItem(BaseModel):
    id: str
    label: str
    type: str = "entity"


class GraphEdgeItem(BaseModel):
    source: str
    target: str
    label: str = "related_to"


class GraphPreviewItem(BaseModel):
    nodes: List[GraphNodeItem] = Field(default_factory=list)
    edges: List[GraphEdgeItem] = Field(default_factory=list)


class GraphEvidenceItem(BaseModel):
    seed_entity_keys: List[str] = Field(default_factory=list)
    preview: GraphPreviewItem = Field(default_factory=GraphPreviewItem)


class ChatResponse(BaseModel):
    answer: str
    citations: List[CitationItem] = Field(default_factory=list)
    sources: List[SourceItem] = Field(default_factory=list)
    entities: List[EntityItem] = Field(default_factory=list)
    graph_evidence: GraphEvidenceItem = Field(default_factory=GraphEvidenceItem)


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
DOCUMENT_STORE: dict[str, DocumentResponse] = {}
CHUNK_STORE: dict[str, dict[str, str]] = {}
UPLOAD_DIR = Path("/data/uploads")
DOCUMENT_METADATA: dict[str, dict[str, str]] = {}
DOCUMENT_ENTITY_TYPES: dict[str, list[str]] = {}

GRAPH_PREVIEW_DEFAULT_NODE_LIMIT = 50
GRAPH_PREVIEW_DEFAULT_EDGE_LIMIT = 100
GRAPH_DOCUMENT_MAX_NODES = 200
GRAPH_DOCUMENT_MAX_EDGES = 400

_BULLET_PATTERN = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_PERSON_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b")
_COMPANY_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z&.-]*(?:\s+[A-Z][A-Za-z&.-]*)*\s+(?:Inc|LLC|Ltd|GmbH|AG|Corp|Corporation|Company))\b"
)
_PERSON_BLOCKED_TOKENS = {
    "am",
    "an",
    "auf",
    "aus",
    "beim",
    "das",
    "dem",
    "den",
    "der",
    "des",
    "die",
    "ein",
    "eine",
    "einem",
    "einen",
    "einer",
    "eines",
    "für",
    "im",
    "in",
    "mit",
    "nach",
    "seit",
    "um",
    "von",
    "vom",
    "vor",
    "zum",
    "zur",
}
_PERSON_BLOCKED_SUFFIXES = {
    "hauptsitz",
    "jahr",
}
_ENTITY_PREFIX_BLACKLIST = {
    "automobilzulieferer",
    "softwareanbieter",
    "unternehmen",
    "firma",
    "hersteller",
    "anbieter",
    "startup",
    "konzern",
}
_GENERIC_COMPANY_TERMS = {
    "solutions",
    "systems",
    "technology",
    "group",
    "services",
    "international",
    "global",
}
_COMPANY_SUFFIXES = {
    "ag",
    "gmbh",
    "inc",
    "ltd",
    "corp",
    "corporation",
    "group",
    "holding",
    "solutions",
    "systems",
}
_REMOVABLE_COMPANY_SUFFIXES = {
    "group",
    "holding",
    "solutions",
    "systems",
    "technology",
    "services",
    "international",
    "global",
}
_COUNTRY_SUFFIX_MAP = {"AT": "AG", "DE": "GmbH", "US": "Inc"}
_COMPANY_INDICATOR_SUFFIXES = {"ag", "gmbh", "inc", "ltd", "corp", "corporation"}
_CANDIDATE_ALIASES = {
    "person": "person",
    "people": "person",
    "persons": "person",
    "company": "company",
    "companies": "company",
    "org": "company",
    "organization": "company",
}
_GLINER_LABELS = [
    "person",
    "organization",
    "company",
    "product",
    "technology",
    "location",
    "project",
    "document",
]
_TYPE_ALIASES = {
    "person": "person",
    "organization": "organization",
    "company": "company",
    "org": "organization",
    "product": "product",
    "technology": "technology",
    "tech": "technology",
    "location": "location",
    "project": "project",
    "document": "document",
}
_RELATION_TYPES = {"WORKS_FOR", "PRODUCES"}
_GLINER_MODEL = None
_GLINER_MODEL_FAILED = False

_OPENAI_CLIENT = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def _looks_like_person(name: str) -> bool:
    parts = [part.strip() for part in name.split() if part.strip()]
    if len(parts) != 2:
        return False

    first, last = parts[0].lower(), parts[1].lower()
    if first in _PERSON_BLOCKED_TOKENS:
        return False
    if last in _PERSON_BLOCKED_SUFFIXES:
        return False
    return True


def _is_list_block(block: str) -> bool:
    lines = [line for line in (part.strip() for part in block.splitlines()) if line]
    return bool(lines) and all(_BULLET_PATTERN.match(line) for line in lines)


def _split_text_by_size(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    words = text.split()
    current_words: list[str] = []
    current_length = 0
    for word in words:
        projected_length = current_length + len(word) + (1 if current_words else 0)
        if current_words and projected_length > CHUNK_SIZE:
            chunks.append(" ".join(current_words))
            current_words = [word]
            current_length = len(word)
            continue

        current_words.append(word)
        current_length = projected_length

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def _merge_short_chunks(chunks: list[str]) -> list[str]:
    min_chars = max(CHUNK_MIN_CHARS, 1)
    if min_chars <= 1:
        return chunks

    merged: list[str] = []
    pending = ""
    for chunk in chunks:
        if len(chunk) < min_chars:
            pending = f"{pending}\n\n{chunk}".strip() if pending else chunk
            continue

        if pending:
            combined = f"{pending}\n\n{chunk}".strip()
            if len(combined) <= CHUNK_SIZE:
                merged.append(combined)
                pending = ""
                continue
            merged.extend(_split_text_by_size(pending))
            pending = ""

        merged.append(chunk)

    if pending:
        if merged:
            combined = f"{merged[-1]}\n\n{pending}".strip()
            if len(combined) <= CHUNK_SIZE:
                merged[-1] = combined
            else:
                merged.extend(_split_text_by_size(pending))
        else:
            merged.extend(_split_text_by_size(pending))

    return merged


def _chunk_text(text: str) -> list[str]:
    raw_blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not raw_blocks:
        raw_blocks = [text.strip()]

    chunks: list[str] = []
    fallback_blocks: list[str] = []
    for block in raw_blocks:
        is_list = _is_list_block(block)
        should_chunk_block = CHUNK_BULLET_LISTS_ENABLED if is_list else CHUNK_PARAGRAPHS_ENABLED
        if should_chunk_block:
            if fallback_blocks:
                chunks.extend(_split_text_by_size("\n\n".join(fallback_blocks)))
                fallback_blocks = []
            chunks.extend(_split_text_by_size(block))
        else:
            fallback_blocks.append(block)

    if fallback_blocks:
        chunks.extend(_split_text_by_size("\n\n".join(fallback_blocks)))

    return _merge_short_chunks(chunks)


def _normalize_entity_candidates(candidates: list[str] | None) -> set[str]:
    if not candidates:
        return {"person", "company", "organization", "product", "technology", "project"}
    normalized = {
        _CANDIDATE_ALIASES.get(candidate.strip().lower(), candidate.strip().lower())
        for candidate in candidates
        if candidate.strip()
    }
    return normalized or {"person", "company", "organization", "product", "technology", "project"}


def _normalize_entity_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^\w\s]", "", normalized.lower())
    return " ".join(normalized.split())


def clean_entity_name(entity_text: str) -> str:
    tokens = [token for token in re.split(r"\s+", entity_text.strip()) if token]
    while tokens and tokens[0].lower().strip(".,") in _ENTITY_PREFIX_BLACKLIST:
        tokens.pop(0)
    return " ".join(tokens)


def normalize_company_name(name: str) -> str:
    tokens = [token.strip(".,") for token in name.split() if token.strip(".,")]
    if not tokens:
        return ""

    mapped_country_suffix = None
    if tokens[-1].upper() in _COUNTRY_SUFFIX_MAP:
        mapped_country_suffix = _COUNTRY_SUFFIX_MAP[tokens[-1].upper()]
        tokens[-1] = mapped_country_suffix

    while len(tokens) > 1 and tokens[-1].lower() in _REMOVABLE_COMPANY_SUFFIXES:
        tokens.pop()

    if not tokens:
        return ""

    original_suffix = name.split()[-1].strip(".,") if name.split() else ""
    mapped_suffix = _COUNTRY_SUFFIX_MAP.get(original_suffix.upper())
    if mapped_suffix and mapped_country_suffix is None:
        tokens.append(mapped_suffix)

    return " ".join(tokens)


def canonical_company_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [token for token in cleaned.split() if token]
    tokens = [token for token in tokens if token not in _COMPANY_SUFFIXES]
    return " ".join(tokens)


def filter_false_entities(entity: dict[str, Any]) -> bool:
    name = str(entity.get("name", "")).strip()
    original_name = str(entity.get("original_name", name)).strip()
    entity_type = _canonical_entity_type(str(entity.get("type", "")).strip())
    if not name:
        return False

    tokens = name.split()
    if entity_type == "person":
        return len(tokens) >= 2 and _looks_like_person(name)

    if len(tokens) == 1 and not re.search(r"[A-ZÄÖÜ][a-zäöüß]+|[A-Z]{2,}", name):
        return False

    lowered_tokens = [token.lower().strip(".,") for token in tokens]
    original_tokens = [token.lower().strip(".,") for token in original_name.split() if token.strip(".,")]
    has_generic_only = any(token in _GENERIC_COMPANY_TERMS for token in original_tokens)
    has_indicator = any(token in _COMPANY_INDICATOR_SUFFIXES for token in lowered_tokens)
    if has_generic_only and not has_indicator:
        return False

    return True


def _capitalization_score(name: str) -> float:
    tokens = [token for token in re.split(r"\s+", name.strip()) if token]
    if not tokens:
        return 0.0
    capped = min(1.0, sum(1 for t in tokens if t[:1].isupper()) / len(tokens))
    return round(capped, 4)


def _entity_confidence_score(entity: dict[str, Any]) -> float:
    ner_confidence = max(0.0, min(1.0, float(entity.get("confidence", 0.0) or 0.0)))
    frequency = float(entity.get("frequency", 1.0) or 1.0)
    frequency_score = min(1.0, frequency / 3.0)
    capitalization = _capitalization_score(str(entity.get("name", "")))
    return round((0.5 * ner_confidence) + (0.3 * frequency_score) + (0.2 * capitalization), 4)


def _canonical_entity_type(entity_type: str) -> str:
    return _TYPE_ALIASES.get(entity_type.strip().lower(), entity_type.strip().lower())


def _build_entity(name: str, entity_type: str, confidence: float = 0.0, source: str = "rule") -> dict[str, Any]:
    canonical_name = " ".join(name.split()).strip()
    canonical_type = _canonical_entity_type(entity_type)
    return {
        "name": canonical_name,
        "canonical_name": canonical_name,
        "normalized_name": _normalize_entity_name(canonical_name),
        "type": canonical_type,
        "confidence": max(0.0, min(1.0, confidence)),
        "source": source,
        "key": f"{canonical_type}:{_normalize_entity_name(canonical_name)}",
    }


def _get_gliner_model():
    global _GLINER_MODEL, _GLINER_MODEL_FAILED
    if _GLINER_MODEL is not None or _GLINER_MODEL_FAILED or GLiNER is None:
        return _GLINER_MODEL
    try:
        _GLINER_MODEL = GLiNER.from_pretrained("numind/NuNerZero")
    except Exception:
        _GLINER_MODEL_FAILED = True
    return _GLINER_MODEL


def extract_entities_gliner(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        return []
    model = _get_gliner_model()
    if model is None:
        return []

    try:
        raw_entities = model.predict_entities(text, _GLINER_LABELS)
    except Exception:
        return []

    entities: list[dict[str, Any]] = []
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        name = str(item.get("text", "")).strip()
        entity_type = _canonical_entity_type(str(item.get("label", "")).strip())
        score = float(item.get("score", 0.0) or 0.0)
        if not name or not entity_type:
            continue
        entities.append(_build_entity(name, entity_type, confidence=score, source="gliner"))
    return entities


def _extract_entities_with_llm(text: str, candidates: set[str]) -> list[dict[str, Any]]:
    if _OPENAI_CLIENT is None or not text.strip() or not candidates:
        return []

    allowed = [candidate.upper() for candidate in sorted(candidates)]
    prompt = (
        "TASK:\n"
        "Extract entities from the following text.\n\n"
        "Return ONLY JSON.\n\n"
        "Entity types allowed:\n"
        + "\n".join(allowed)
        + "\n\nRules:\n"
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

    try:
        response = _OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are an expert knowledge graph extraction engine."},
                {"role": "user", "content": prompt},
            ],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception:
        return []

    entities: list[dict[str, Any]] = []
    for item in payload.get("entities", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        entity_type = _canonical_entity_type(str(item.get("type", "")).strip())
        if not name or entity_type not in candidates:
            continue
        entities.append(_build_entity(name, entity_type, confidence=0.75, source="llm"))
    return entities


def _extract_entities_regex(text: str, requested: set[str]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    if "company" in requested or "organization" in requested:
        for match in _COMPANY_PATTERN.findall(text):
            entities.append(_build_entity(match.strip(), "company", confidence=0.65, source="regex"))

    if "person" in requested:
        for match in _PERSON_PATTERN.findall(text):
            name = match.strip()
            if not _looks_like_person(name):
                continue
            if _COMPANY_PATTERN.search(name):
                continue
            entities.append(_build_entity(name, "person", confidence=0.6, source="regex"))
    return entities


def merge_entities(*entity_lists: list[dict[str, Any]], threshold: float = 0.9) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for entities in entity_lists:
        for entity in entities:
            norm = str(entity.get("normalized_name") or _normalize_entity_name(str(entity.get("name", ""))))
            if not norm:
                continue
            matched = None
            for existing in merged:
                if existing["type"] != entity.get("type"):
                    continue
                score = 0.0
                if fuzz is not None:
                    score = float(fuzz.ratio(norm, existing["normalized_name"])) / 100.0
                elif norm == existing["normalized_name"]:
                    score = 1.0
                if score >= threshold:
                    matched = existing
                    break
            if matched is None:
                merged.append(dict(entity, normalized_name=norm, frequency=1))
            else:
                matched["frequency"] = int(matched.get("frequency", 1)) + 1
                matched["confidence"] = max(float(matched.get("confidence", 0.0)), float(entity.get("confidence", 0.0)))
                if len(str(entity.get("canonical_name", ""))) > len(str(matched.get("canonical_name", ""))):
                    matched["name"] = entity.get("name", matched["name"])
                    matched["canonical_name"] = entity.get("canonical_name", matched.get("canonical_name"))
    return merged


def link_entity(entity_name: str, entity_type: str = "") -> dict[str, str | None]:
    canonical_name = " ".join(entity_name.split()).strip()
    return {
        "name": entity_name,
        "canonical_name": canonical_name,
        "wikidata_id": None,
        "type": _canonical_entity_type(entity_type) if entity_type else "unknown",
    }


def _rank_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for entity in entities:
        score = _entity_confidence_score(entity)
        if score < 0.4:
            continue
        enriched = dict(entity)
        enriched["score"] = score
        ranked.append(enriched)
    return ranked


def _post_process_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    processed: list[dict[str, Any]] = []
    for entity in entities:
        entity_type = _canonical_entity_type(str(entity.get("type", "")))
        original_name = str(entity.get("name", "")).strip()
        cleaned_name = clean_entity_name(original_name)
        normalized_name = normalize_company_name(cleaned_name) if entity_type in {"company", "organization"} else cleaned_name
        canonical_name = canonical_company_name(normalized_name) if entity_type in {"company", "organization"} else _normalize_entity_name(normalized_name)

        logging.info(
            "entity_post_processing original=%s cleaned=%s normalized=%s canonical=%s",
            original_name,
            cleaned_name,
            normalized_name,
            canonical_name,
        )

        candidate = dict(entity)
        candidate["original_name"] = original_name
        candidate["name"] = normalized_name
        candidate["canonical_name"] = canonical_name
        candidate["normalized_name"] = _normalize_entity_name(normalized_name)
        candidate["key"] = f"{entity_type}:{candidate['normalized_name']}"
        candidate["type"] = entity_type

        if not filter_false_entities(candidate):
            continue
        processed.append(candidate)

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for entity in processed:
        dedupe_key = (entity["type"], str(entity.get("canonical_name", "")))
        existing = deduped.get(dedupe_key)
        if existing is None:
            deduped[dedupe_key] = dict(entity)
            continue
        existing["frequency"] = int(existing.get("frequency", 1)) + int(entity.get("frequency", 1))
        existing["confidence"] = max(float(existing.get("confidence", 0.0)), float(entity.get("confidence", 0.0)))

    return list(deduped.values())


def _extract_entities(text: str, candidates: list[str] | None = None) -> list[dict[str, Any]]:
    requested = _normalize_entity_candidates(candidates)
    gliner_entities = [e for e in extract_entities_gliner(text) if e["type"] in requested]
    llm_entities = _extract_entities_with_llm(text, requested)
    regex_entities = _extract_entities_regex(text, requested)
    merged = merge_entities(gliner_entities, llm_entities, regex_entities, threshold=0.9)
    post_processed = _post_process_entities(merged)
    ranked = _rank_entities(post_processed)

    output: list[dict[str, Any]] = []
    for entity in ranked:
        linked = link_entity(entity.get("canonical_name", entity.get("name", "")), entity.get("type", ""))
        output.append(
            {
                "key": entity["key"],
                "name": entity["name"],
                "type": entity["type"],
                "canonical_name": linked["canonical_name"],
                "confidence": entity.get("score", entity.get("confidence", 0.0)),
                "score": entity.get("score", 0.0),
                "wikidata_id": linked["wikidata_id"],
            }
        )
    return output


async def extract_entities_batch(chunks: list[str], candidates: list[str] | None = None) -> list[list[dict[str, Any]]]:
    tasks = [asyncio.to_thread(_extract_entities, chunk, candidates) for chunk in chunks]
    return await asyncio.gather(*tasks)


def extract_relationships_llm(text: str) -> list[dict[str, str]]:
    if _OPENAI_CLIENT is None or not text.strip():
        return []
    prompt = (
        "Extract relationships and return strict JSON with shape "
        "{\"relationships\":[{\"source\":\"...\",\"target\":\"...\",\"type\":\"WORKS_FOR\"}]}. "
        "Allowed relationship types: WORKS_FOR, PRODUCES. "
        f"Text: {text}"
    )
    try:
        response = _OPENAI_CLIENT.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You extract graph relationships in JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception:
        return []

    relationships: list[dict[str, str]] = []
    for item in payload.get("relationships", []):
        if not isinstance(item, dict):
            continue
        rel_type = str(item.get("type", "")).strip().upper()
        source = str(item.get("source", "")).strip()
        target = str(item.get("target", "")).strip()
        if rel_type not in _RELATION_TYPES or not source or not target:
            continue
        relationships.append({"source": source, "target": target, "type": rel_type})
    return relationships


def evaluate_entity_extraction(predicted: list[dict[str, Any]], reference: list[dict[str, str]]) -> dict[str, float | int]:
    predicted_set = {(str(e.get("name", "")).lower(), str(e.get("type", "")).lower()) for e in predicted}
    reference_set = {(str(e.get("name", "")).lower(), str(e.get("type", "")).lower()) for e in reference}
    true_positive = len(predicted_set & reference_set)
    precision = true_positive / len(predicted_set) if predicted_set else 0.0
    recall = true_positive / len(reference_set) if reference_set else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "entity_frequency": len(predicted),
    }


def build_graph_entities_output(entities: list[dict[str, Any]], relationships: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    return {"entities": entities, "relationships": relationships}


def _summarize_document_entities(doc_id: str) -> tuple[int, list[dict[str, str | int]]]:
    entity_counts: dict[tuple[str, str], dict[str, str | int]] = {}

    for vector_item in VECTOR_STORE:
        if vector_item.source != doc_id:
            continue
        for entity in vector_item.entities:
            entity_type = str(entity.get("type", "unknown"))
            entity_name = str(entity.get("name", ""))
            entity_key = str(entity.get("key", f"{entity_type}:{entity_name.lower()}"))
            dedupe_key = (entity_type.lower(), entity_name.lower())
            if dedupe_key not in entity_counts:
                entity_counts[dedupe_key] = {
                    "key": entity_key,
                    "name": entity_name,
                    "type": entity_type,
                    "mentions": 0,
                }
            entity_counts[dedupe_key]["mentions"] = int(entity_counts[dedupe_key]["mentions"]) + 1

    entities = sorted(
        entity_counts.values(),
        key=lambda item: (-int(item["mentions"]), str(item["name"]).lower()),
    )
    return len(entities), entities


def _persist_document_neo4j(document: DocumentResponse, chunks: list[tuple[str, str]], chunk_entities: dict[str, list[dict[str, Any]]] | None = None) -> None:
    if not (GraphDatabase and NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        session.run(
            """
            MERGE (d:Document {doc_id: $doc_id})
            SET d.title = $title,
                d.file_name = $file_name,
                d.uploaded_at = datetime($uploaded_at),
                d.chunk_count = $chunk_count
            """,
            doc_id=document.doc_id,
            title=document.title,
            file_name=document.file_name,
            uploaded_at=document.uploaded_at.isoformat(),
            chunk_count=document.chunk_count,
        )

        for chunk_id, chunk_text in chunks:
            session.run(
                """
                MATCH (d:Document {doc_id: $doc_id})
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.doc_id = $doc_id, c.text = $text
                MERGE (d)-[:HAS_CHUNK]->(c)
                """,
                doc_id=document.doc_id,
                chunk_id=chunk_id,
                text=chunk_text,
            )
            for entity in (chunk_entities or {}).get(chunk_id, []):
                session.run(
                    """
                    MATCH (c:Chunk {chunk_id: $chunk_id})
                    MERGE (e:Entity {canonical_name: $canonical_name})
                    SET e.name = $name,
                        e.type = $type,
                        e.confidence = $confidence,
                        e.score = $score,
                        e.wikidata_id = $wikidata_id
                    MERGE (c)-[:MENTIONS]->(e)
                    """,
                    chunk_id=chunk_id,
                    name=entity.get("name", ""),
                    type=entity.get("type", "unknown"),
                    canonical_name=entity.get("canonical_name", entity.get("name", "")),
                    confidence=float(entity.get("confidence", 0.0) or 0.0),
                    score=float(entity.get("score", 0.0) or 0.0),
                    wikidata_id=entity.get("wikidata_id"),
                )
            for relation in extract_relationships_llm(chunk_text):
                session.run(
                    """
                    MERGE (src:Entity {name: $source_name})
                    MERGE (dst:Entity {name: $target_name})
                    MERGE (src)-[r:RELATES {type: $rel_type}]->(dst)
                    """,
                    source_name=relation["source"],
                    target_name=relation["target"],
                    rel_type=relation["type"],
                )
    driver.close()


def _delete_document_neo4j(doc_id: str) -> None:
    if not (GraphDatabase and NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD):
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        session.run(
            """
            MATCH (d:Document {doc_id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
            DETACH DELETE c
            """,
            doc_id=doc_id,
        )
        session.run("MATCH (d:Document {doc_id: $doc_id}) DETACH DELETE d", doc_id=doc_id)
    driver.close()


def _delete_embeddings_milvus(doc_id: str) -> None:
    if not (MilvusClient and MILVUS_URI):
        return

    client = MilvusClient(uri=MILVUS_URI)
    try:
        client.delete(collection_name="chunks", filter=f'doc_id == "{doc_id}"')
    except Exception:
        return


def retrieval(question: str, k: int = 3, entity_candidates: list[str] | None = None) -> List[Document]:
    """Return the top-k most relevant docs using a simple token overlap score."""
    question_terms = set(question.lower().split())
    scored: List[tuple[int, Document]] = []

    query_entities = {
        entity["key"] for entity in _extract_entities(question, candidates=entity_candidates)
    }

    for doc in VECTOR_STORE:
        doc_terms = set(doc.content.lower().split())
        lexical_score = len(question_terms & doc_terms)
        doc_entity_keys = {entity["key"] for entity in doc.entities}
        entity_score = len(query_entities & doc_entity_keys) * 3
        score = lexical_score + entity_score
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


def build_graph_preview(
    entity_keys: list[str],
    max_nodes: int = GRAPH_PREVIEW_DEFAULT_NODE_LIMIT,
    max_edges: int = GRAPH_PREVIEW_DEFAULT_EDGE_LIMIT,
) -> dict[str, list[dict[str, str]]]:
    bounded_max_nodes = max(0, max_nodes)
    bounded_max_edges = max(0, max_edges)

    capped_keys = entity_keys[:bounded_max_nodes]
    nodes = [{"id": key, "label": key, "type": "entity"} for key in capped_keys]

    edges = [
        {
            "source": capped_keys[index],
            "target": capped_keys[index + 1],
            "label": "related_to",
        }
        for index in range(len(capped_keys) - 1)
    ][:bounded_max_edges]

    return {"nodes": nodes, "edges": edges}


def fetch_document_graph_preview(
    doc_id: str,
    max_nodes: int = GRAPH_DOCUMENT_MAX_NODES,
    max_edges: int = GRAPH_DOCUMENT_MAX_EDGES,
) -> GraphPreviewItem:
    if not NEO4J_URI or not NEO4J_USER or not NEO4J_PASSWORD:
        return _build_document_graph_preview_from_vector_store(
            doc_id=doc_id,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )

    if doc_id == "all":
        query = """
    MATCH (d:Document)-[:HAS_CHUNK]->(c)-[:MENTIONS]->(e)
    OPTIONAL MATCH (e)-[r]->(e2)
    RETURN
      collect(DISTINCT e) AS entities,
      collect(DISTINCT e2) AS neighbors,
      collect(DISTINCT {
        source: toString(id(e)),
        target: toString(id(e2)),
        label: type(r)
      }) AS raw_edges
    """
        query_params: dict[str, str] = {}
    else:
        query = """
    MATCH (d:Document {doc_id:$doc_id})-[:HAS_CHUNK]->(c)-[:MENTIONS]->(e)
    OPTIONAL MATCH (e)-[r]->(e2)
    RETURN
      collect(DISTINCT e) AS entities,
      collect(DISTINCT e2) AS neighbors,
      collect(DISTINCT {
        source: toString(id(e)),
        target: toString(id(e2)),
        label: type(r)
      }) AS raw_edges
    """
        query_params = {"doc_id": doc_id}

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            record = session.run(query, **query_params).single()

    if record is None:
        return GraphPreviewItem()

    entities = record["entities"] or []
    neighbors = record["neighbors"] or []
    raw_edges = record["raw_edges"] or []

    nodes: list[GraphNodeItem] = []
    node_ids: set[str] = set()
    for node in [*entities, *neighbors]:
        if node is None:
            continue
        node_id = str(node.id)
        if node_id in node_ids:
            continue
        node_ids.add(node_id)

        labels = list(node.labels)
        node_type = labels[0].lower() if labels else "entity"
        nodes.append(
            GraphNodeItem(
                id=node_id,
                label=node.get("name") or node.get("label") or node.get("doc_id") or node_id,
                type=node_type,
            )
        )
        if len(nodes) >= max_nodes:
            break

    allowed_node_ids = {node.id for node in nodes}
    edges: list[GraphEdgeItem] = []
    for edge in raw_edges:
        source = edge.get("source")
        target = edge.get("target")
        if not source or not target:
            continue
        if source not in allowed_node_ids or target not in allowed_node_ids:
            continue
        edges.append(GraphEdgeItem(source=source, target=target, label=edge.get("label") or "related_to"))
        if len(edges) >= max_edges:
            break

    return GraphPreviewItem(nodes=nodes, edges=edges)


def _build_document_graph_preview_from_vector_store(
    doc_id: str,
    max_nodes: int,
    max_edges: int,
) -> GraphPreviewItem:
    bounded_max_nodes = max(0, max_nodes)
    bounded_max_edges = max(0, max_edges)

    relevant_docs = VECTOR_STORE if doc_id == "all" else [item for item in VECTOR_STORE if item.source == doc_id]

    entity_keys: list[str] = []
    seen_entity_keys: set[str] = set()

    for document in relevant_docs:
        for entity in document.entities:
            key = str(entity.get("key", "")).strip()
            if not key or key in seen_entity_keys:
                continue
            seen_entity_keys.add(key)
            entity_keys.append(key)

    if not entity_keys and doc_id != "all":
        fallback_doc_chunks = [chunk_id for chunk_id, chunk in CHUNK_STORE.items() if chunk["doc_id"] == doc_id]
        entity_keys.extend(fallback_doc_chunks)

    preview = build_graph_preview(entity_keys, max_nodes=bounded_max_nodes, max_edges=bounded_max_edges)
    return GraphPreviewItem(**preview)


def _parse_multipart_form_data(body: bytes, content_type: str) -> tuple[list[tuple[str, bytes]], dict[str, str]]:
    boundary_match = re.search(r'boundary="?([^";]+)"?', content_type)
    if not boundary_match:
        raise HTTPException(status_code=400, detail="Missing multipart boundary")

    boundary = boundary_match.group(1).encode("utf-8")
    delimiter = b"--" + boundary
    parts = body.split(delimiter)
    files: list[tuple[str, bytes]] = []
    fields: dict[str, str] = {}

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

        name_match = re.search(r'name="([^"]*)"', content_disposition)
        filename_match = re.search(r'filename="([^"]*)"', content_disposition)
        if filename_match:
            filename = filename_match.group(1)
            files.append((filename, payload.rstrip(b"\r\n")))
            continue

        if not name_match:
            continue

        fields[name_match.group(1)] = payload.rstrip(b"\r\n").decode("utf-8", errors="ignore")

    return files, fields


def _parse_multipart_files(body: bytes, content_type: str) -> list[tuple[str, bytes]]:
    files, _fields = _parse_multipart_form_data(body, content_type)

    return files


def _parse_entity_types(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip().lower() for item in parsed if str(item).strip()]


@app.post("/ingest", response_model=IngestResponse)
async def ingest(request: Request) -> IngestResponse:
    documents: List[str] = []
    entity_candidates = ["person", "company"]
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        payload = IngestRequest.model_validate(body)
        entity_candidates = payload.entity_candidates
        for item in payload.documents:
            if isinstance(item, str):
                text = item.strip()
            else:
                text = (item.get("text") or item.get("content") or "").strip()

            if text:
                documents.append(text)

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

    batch_entities = await extract_entities_batch(documents, entity_candidates)
    for i, (content, entities) in enumerate(zip(documents, batch_entities), start=len(VECTOR_STORE) + 1):
        VECTOR_STORE.append(
            Document(
                id=str(i),
                content=content,
                source=f"doc-{i}",
                entities=entities,
            )
        )

    return IngestResponse(ingested=len(documents))


@app.get("/documents", response_model=list[DocumentResponse])
def list_documents() -> list[DocumentResponse]:
    hydrated_documents: list[DocumentResponse] = []
    for document in DOCUMENT_STORE.values():
        entity_count, entities = _summarize_document_entities(document.doc_id)
        hydrated_documents.append(
            document.model_copy(
                update={
                    "extracted_entity_count": entity_count,
                    "extracted_entities": entities,
                }
            )
        )

    return sorted(hydrated_documents, key=lambda item: item.uploaded_at, reverse=True)


@app.get("/documents/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: str) -> DocumentResponse:
    document = DOCUMENT_STORE.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    entity_count, entities = _summarize_document_entities(doc_id)
    return document.model_copy(update={"extracted_entity_count": entity_count, "extracted_entities": entities})


@app.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(request: Request) -> DocumentResponse:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=415, detail="Unsupported content type")

    files, fields = _parse_multipart_form_data(await request.body(), content_type)
    if not files:
        raise HTTPException(status_code=400, detail="No file provided")

    file_name, raw_content = files[0]
    try:
        text = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text") from exc

    if not text.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    doc_id = str(uuid4())
    upload_time = datetime.now(tz=timezone.utc)
    chunks = _chunk_text(text)
    configured_entity_types = _parse_entity_types(fields.get("entity_types"))

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_file_name = Path(file_name).name
    file_path = UPLOAD_DIR / f"{doc_id}_{safe_file_name}"
    file_path.write_bytes(raw_content)

    document = DocumentResponse(
        doc_id=doc_id,
        title=Path(safe_file_name).stem,
        file_name=safe_file_name,
        uploaded_at=upload_time,
        chunk_count=len(chunks),
    )
    DOCUMENT_STORE[doc_id] = document
    DOCUMENT_METADATA[doc_id] = {}
    DOCUMENT_ENTITY_TYPES[doc_id] = configured_entity_types

    chunk_pairs: list[tuple[str, str]] = []
    chunk_entities_map: dict[str, list[dict[str, Any]]] = {}
    extracted_batch = await extract_entities_batch(chunks, configured_entity_types)
    for chunk_text, entities in zip(chunks, extracted_batch):
        chunk_id = str(uuid4())
        chunk_pairs.append((chunk_id, chunk_text))
        chunk_entities_map[chunk_id] = entities
        CHUNK_STORE[chunk_id] = {"doc_id": doc_id, "text": chunk_text}
        VECTOR_STORE.append(
            Document(
                id=chunk_id,
                content=chunk_text,
                source=doc_id,
                entities=entities,
            )
        )

    _persist_document_neo4j(document, chunk_pairs, chunk_entities_map)

    entity_count, entities = _summarize_document_entities(doc_id)
    return document.model_copy(update={"extracted_entity_count": entity_count, "extracted_entities": entities})


@app.put("/documents/{doc_id}", response_model=DocumentResponse)
def update_document(doc_id: str, payload: DocumentUpdateRequest) -> DocumentResponse:
    document = DOCUMENT_STORE.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    new_title = payload.title.strip() if payload.title else document.title
    updated_document = document.model_copy(update={"title": new_title})
    DOCUMENT_STORE[doc_id] = updated_document
    DOCUMENT_METADATA[doc_id] = payload.metadata
    entity_count, entities = _summarize_document_entities(doc_id)
    return updated_document.model_copy(update={"extracted_entity_count": entity_count, "extracted_entities": entities})


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str) -> dict[str, str]:
    document = DOCUMENT_STORE.pop(doc_id, None)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_ids = [chunk_id for chunk_id, chunk in CHUNK_STORE.items() if chunk["doc_id"] == doc_id]
    for chunk_id in chunk_ids:
        CHUNK_STORE.pop(chunk_id, None)

    VECTOR_STORE[:] = [item for item in VECTOR_STORE if item.source != doc_id]
    DOCUMENT_METADATA.pop(doc_id, None)
    DOCUMENT_ENTITY_TYPES.pop(doc_id, None)

    _delete_document_neo4j(doc_id)
    _delete_embeddings_milvus(doc_id)

    for candidate in UPLOAD_DIR.glob(f"{doc_id}_*"):
        if candidate.is_file():
            candidate.unlink()

    return {"status": "deleted", "doc_id": doc_id}


@app.post("/documents/{doc_id}/reindex")
async def reindex_document(doc_id: str, request: Request) -> dict[str, object]:
    document = DOCUMENT_STORE.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    upload_file = next((candidate for candidate in UPLOAD_DIR.glob(f"{doc_id}_*") if candidate.is_file()), None)
    if upload_file is None:
        raise HTTPException(status_code=404, detail="Uploaded file for document not found")

    raw_content = upload_file.read_bytes()
    try:
        text = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text") from exc

    chunks = _chunk_text(text)
    configured_entity_types = DOCUMENT_ENTITY_TYPES.get(doc_id, [])
    if "application/json" in request.headers.get("content-type", ""):
        payload = await request.json()
        configured_entity_types = _parse_entity_types(json.dumps(payload.get("entity_types", [])))
    DOCUMENT_ENTITY_TYPES[doc_id] = configured_entity_types

    old_chunk_ids = [chunk_id for chunk_id, chunk in CHUNK_STORE.items() if chunk["doc_id"] == doc_id]
    for chunk_id in old_chunk_ids:
        CHUNK_STORE.pop(chunk_id, None)

    VECTOR_STORE[:] = [item for item in VECTOR_STORE if item.source != doc_id]

    chunk_pairs: list[tuple[str, str]] = []
    chunk_entities_map: dict[str, list[dict[str, Any]]] = {}
    extracted_batch = await extract_entities_batch(chunks, configured_entity_types)
    for chunk_text, entities in zip(chunks, extracted_batch):
        chunk_id = str(uuid4())
        chunk_pairs.append((chunk_id, chunk_text))
        chunk_entities_map[chunk_id] = entities
        CHUNK_STORE[chunk_id] = {"doc_id": doc_id, "text": chunk_text}
        VECTOR_STORE.append(
            Document(
                id=chunk_id,
                content=chunk_text,
                source=doc_id,
                entities=entities,
            )
        )

    updated_document = document.model_copy(update={"chunk_count": len(chunks)})
    DOCUMENT_STORE[doc_id] = updated_document

    _delete_document_neo4j(doc_id)
    _persist_document_neo4j(updated_document, chunk_pairs, chunk_entities_map)
    _delete_embeddings_milvus(doc_id)

    return {"reindexed": True, "doc_id": doc_id, "chunk_count": len(chunks)}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    question = payload.query or payload.question or ""
    docs = retrieval(question, k=payload.top_k, entity_candidates=payload.entity_candidates)
    answer = generate_answer(question, docs)

    sources = [
        SourceItem(
            source_id=f"S{index}",
            doc_id=d.source,
            chunk_id=d.id,
            score=1.0,
            title=d.source,
            snippet=d.content,
            text=d.content,
        )
        for index, d in enumerate(docs, start=1)
    ]
    citations = [
        CitationItem(marker=f"[{source.source_id}]", chunk_id=source.chunk_id, doc_id=source.doc_id, score=source.score)
        for source in sources
    ]

    seed_entity_keys = [source.doc_id for source in sources]
    preview_data = build_graph_preview(seed_entity_keys)

    response_entities: list[EntityItem] = []
    seen_entity_keys: set[str] = set()
    for doc in docs:
        for entity in doc.entities:
            if entity["key"] in seen_entity_keys:
                continue
            seen_entity_keys.add(entity["key"])
            response_entities.append(
                EntityItem(
                    key=entity["key"],
                    name=entity["name"],
                    type=entity["type"],
                    salience=1.0,
                    source_chunk_ids=[doc.id],
                )
            )

    return ChatResponse(
        answer=answer,
        citations=citations,
        sources=sources,
        entities=response_entities,
        graph_evidence=GraphEvidenceItem(
            seed_entity_keys=seed_entity_keys,
            preview=GraphPreviewItem(**preview_data),
        ),
    )


@app.get("/graph/preview")
def graph_preview(
    entity_keys: str = "",
    max_nodes: int = GRAPH_PREVIEW_DEFAULT_NODE_LIMIT,
    max_edges: int = GRAPH_PREVIEW_DEFAULT_EDGE_LIMIT,
) -> dict[str, list[dict[str, str]]]:
    keys = [key.strip() for key in entity_keys.split(",") if key.strip()]
    return build_graph_preview(keys, max_nodes=max_nodes, max_edges=max_edges)


@app.get("/graph/document/{doc_id}", response_model=GraphPreviewItem)
def graph_document(doc_id: str) -> GraphPreviewItem:
    return fetch_document_graph_preview(
        doc_id=doc_id,
        max_nodes=GRAPH_DOCUMENT_MAX_NODES,
        max_edges=GRAPH_DOCUMENT_MAX_EDGES,
    )


@app.get("/evidence")
def evidence(chunk_ids: str = "") -> dict[str, list[dict[str, str]]]:
    requested_chunk_ids = {chunk_id.strip() for chunk_id in chunk_ids.split(",") if chunk_id.strip()}

    if requested_chunk_ids:
        matched_documents = [document for document in VECTOR_STORE if document.id in requested_chunk_ids]
    else:
        matched_documents = []

    return {
        "chunks": [
            {
                "chunk_id": document.id,
                "doc_id": document.source,
                "title": document.source,
                "text": document.content,
            }
            for document in matched_documents
        ]
    }
