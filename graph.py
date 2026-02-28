from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class Document:
    """A source document.

    `doc_id` is unique across the graph.
    """

    doc_id: str
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class Chunk:
    """A text chunk that belongs to a document.

    `chunk_id` is unique across the graph.
    """

    chunk_id: str
    doc_id: str
    text: str = ""
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class Entity:
    """A canonicalized entity extracted from chunks.

    `key` is unique across the graph.
    """

    key: str
    label: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)


class GraphStore:
    """In-memory graph store with upsert semantics and simple subgraph fetch.

    Constraints enforced:
    - Document(doc_id) unique
    - Chunk(chunk_id) unique
    - Entity(key) unique
    """

    def __init__(self) -> None:
        self.documents: Dict[str, Document] = {}
        self.chunks: Dict[str, Chunk] = {}
        self.entities: Dict[str, Entity] = {}

        # Edges
        self.doc_to_chunks: Dict[str, Set[str]] = {}
        self.chunk_to_entities: Dict[str, Set[str]] = {}
        self.entity_to_chunks: Dict[str, Set[str]] = {}

    def upsert_document(self, doc_id: str, metadata: Optional[Dict[str, object]] = None) -> Document:
        """Insert or update a document by `doc_id` (unique key)."""
        if doc_id in self.documents:
            if metadata:
                self.documents[doc_id].metadata.update(metadata)
            return self.documents[doc_id]

        document = Document(doc_id=doc_id, metadata=dict(metadata or {}))
        self.documents[doc_id] = document
        self.doc_to_chunks.setdefault(doc_id, set())
        return document

    def upsert_chunk(
        self,
        chunk_id: str,
        doc_id: str,
        text: str = "",
        metadata: Optional[Dict[str, object]] = None,
    ) -> Chunk:
        """Insert or update a chunk by `chunk_id` (unique key)."""
        self.upsert_document(doc_id)

        if chunk_id in self.chunks:
            chunk = self.chunks[chunk_id]

            # Re-link to a new document if changed.
            if chunk.doc_id != doc_id:
                self.doc_to_chunks.setdefault(chunk.doc_id, set()).discard(chunk_id)
                chunk.doc_id = doc_id
                self.doc_to_chunks.setdefault(doc_id, set()).add(chunk_id)

            if text:
                chunk.text = text
            if metadata:
                chunk.metadata.update(metadata)
            return chunk

        chunk = Chunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            text=text,
            metadata=dict(metadata or {}),
        )
        self.chunks[chunk_id] = chunk
        self.doc_to_chunks.setdefault(doc_id, set()).add(chunk_id)
        self.chunk_to_entities.setdefault(chunk_id, set())
        return chunk

    def upsert_entity(
        self,
        key: str,
        label: Optional[str] = None,
        metadata: Optional[Dict[str, object]] = None,
    ) -> Entity:
        """Insert or update an entity by `key` (unique key)."""
        if key in self.entities:
            entity = self.entities[key]
            if label is not None:
                entity.label = label
            if metadata:
                entity.metadata.update(metadata)
            return entity

        entity = Entity(key=key, label=label, metadata=dict(metadata or {}))
        self.entities[key] = entity
        self.entity_to_chunks.setdefault(key, set())
        return entity

    def link_chunk_mentions_entities(self, chunk_id: str, entity_keys: Iterable[str]) -> List[Tuple[str, str, str]]:
        """Link a chunk to a set of mentioned entities.

        Returns created/confirmed edges as tuples: ("Chunk", chunk_id, entity_key).
        """
        if chunk_id not in self.chunks:
            raise KeyError(f"Chunk '{chunk_id}' does not exist. Upsert it first.")

        linked_edges: List[Tuple[str, str, str]] = []
        chunk_entities = self.chunk_to_entities.setdefault(chunk_id, set())

        for key in entity_keys:
            self.upsert_entity(key)
            if key not in chunk_entities:
                chunk_entities.add(key)
                self.entity_to_chunks.setdefault(key, set()).add(chunk_id)
            linked_edges.append(("Chunk", chunk_id, key))

        return linked_edges

    def fetch_subgraph(self, entity_keys: Iterable[str], hops: int = 2) -> Dict[str, object]:
        """Fetch an induced subgraph around a set of entities.

        Traversal alternates over edges:
        Entity <-> Chunk <-> Document

        `hops` is the maximum graph distance from start entities.
        """
        if hops < 0:
            raise ValueError("hops must be >= 0")

        start_keys = [k for k in entity_keys if k in self.entities]
        visited_entities: Set[str] = set(start_keys)
        visited_chunks: Set[str] = set()
        visited_documents: Set[str] = set()

        frontier_entities: Set[str] = set(start_keys)
        frontier_chunks: Set[str] = set()
        frontier_documents: Set[str] = set()

        for depth in range(1, hops + 1):
            if depth % 2 == 1:
                # From entity -> chunks
                next_chunks: Set[str] = set()
                for entity_key in frontier_entities:
                    next_chunks.update(self.entity_to_chunks.get(entity_key, set()))
                next_chunks -= visited_chunks
                visited_chunks.update(next_chunks)
                frontier_chunks = next_chunks
                frontier_entities = set()
            else:
                # From chunk -> entities and documents
                next_entities: Set[str] = set()
                next_documents: Set[str] = set()

                for chunk_id in frontier_chunks:
                    chunk = self.chunks.get(chunk_id)
                    if not chunk:
                        continue
                    next_entities.update(self.chunk_to_entities.get(chunk_id, set()))
                    next_documents.add(chunk.doc_id)

                next_entities -= visited_entities
                next_documents -= visited_documents

                visited_entities.update(next_entities)
                visited_documents.update(next_documents)

                frontier_entities = next_entities
                frontier_documents = next_documents
                frontier_chunks = set()

        # Build edge lists limited to visited nodes
        chunk_entity_edges: List[Tuple[str, str]] = []
        for chunk_id in visited_chunks:
            for entity_key in self.chunk_to_entities.get(chunk_id, set()):
                if entity_key in visited_entities:
                    chunk_entity_edges.append((chunk_id, entity_key))

        doc_chunk_edges: List[Tuple[str, str]] = []
        for doc_id, chunk_ids in self.doc_to_chunks.items():
            if doc_id not in visited_documents:
                continue
            for chunk_id in chunk_ids:
                if chunk_id in visited_chunks:
                    doc_chunk_edges.append((doc_id, chunk_id))

        return {
            "documents": {doc_id: self.documents[doc_id] for doc_id in visited_documents},
            "chunks": {chunk_id: self.chunks[chunk_id] for chunk_id in visited_chunks},
            "entities": {key: self.entities[key] for key in visited_entities},
            "edges": {
                "document_contains_chunk": doc_chunk_edges,
                "chunk_mentions_entity": chunk_entity_edges,
            },
        }
