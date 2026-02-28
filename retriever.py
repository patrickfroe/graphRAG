from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol, Sequence


class Embedder(Protocol):
    def embed(self, text: str) -> List[float]:
        ...


class MilvusSearcher(Protocol):
    def search(self, vector: List[float], top_k: int) -> Sequence[Dict[str, Any]]:
        ...


class GraphExpander(Protocol):
    def expand(self, entities: Sequence[str], max_facts: int) -> Sequence[Dict[str, Any]]:
        ...


@dataclass
class RetrievalResult:
    context: str
    sources: Dict[str, List[Dict[str, Any]]]


class OpenAIEmbedder:
    """OpenAI embedding wrapper.

    Expects an initialized OpenAI client that supports:
      client.embeddings.create(model=..., input=...)
    """

    def __init__(self, client: Any, model: str = "text-embedding-3-small") -> None:
        self.client = client
        self.model = model

    def embed(self, text: str) -> List[float]:
        response = self.client.embeddings.create(model=self.model, input=text)
        return list(response.data[0].embedding)


class MilvusClientSearcher:
    """Milvus search wrapper.

    Expects a collection object that supports:
      collection.search(data=[vector], anns_field=..., limit=..., output_fields=[...])
    """

    def __init__(
        self,
        collection: Any,
        anns_field: str = "embedding",
        output_fields: Sequence[str] = ("chunk_id", "text", "doc_id", "entities"),
    ) -> None:
        self.collection = collection
        self.anns_field = anns_field
        self.output_fields = list(output_fields)

    def search(self, vector: List[float], top_k: int) -> Sequence[Dict[str, Any]]:
        results = self.collection.search(
            data=[vector],
            anns_field=self.anns_field,
            limit=top_k,
            output_fields=self.output_fields,
        )
        normalized: List[Dict[str, Any]] = []
        for hit in results[0]:
            entity = hit.entity
            normalized.append(
                {
                    "chunk_id": entity.get("chunk_id"),
                    "doc_id": entity.get("doc_id"),
                    "text": entity.get("text", ""),
                    "entities": entity.get("entities") or [],
                    "score": float(hit.score),
                }
            )
        return normalized


class Neo4jGraphExpander:
    """Neo4j entity expansion wrapper.

    Expects an initialized Neo4j driver.
    """

    def __init__(self, driver: Any) -> None:
        self.driver = driver

    def expand(self, entities: Sequence[str], max_facts: int) -> Sequence[Dict[str, Any]]:
        if not entities:
            return []

        query = """
        UNWIND $entities AS name
        MATCH (e:Entity {name: name})-[r]-(n)
        RETURN e.name AS entity,
               type(r) AS relation,
               n.name AS neighbor,
               coalesce(r.source, 'neo4j') AS source
        LIMIT $max_facts
        """
        with self.driver.session() as session:
            records = session.run(query, entities=list(set(entities)), max_facts=max_facts)
            return [
                {
                    "entity": record["entity"],
                    "relation": record["relation"],
                    "neighbor": record["neighbor"],
                    "source": record["source"],
                }
                for record in records
            ]


class GraphRAGRetriever:
    def __init__(self, embedder: Embedder, searcher: MilvusSearcher, expander: GraphExpander) -> None:
        self.embedder = embedder
        self.searcher = searcher
        self.expander = expander

    def retrieve(self, query: str, top_k: int = 5, max_graph_facts: int = 20) -> RetrievalResult:
        # 1) embed query via OpenAI
        query_vector = self.embedder.embed(query)

        # 2) Milvus search -> top chunks
        chunks = list(self.searcher.search(query_vector, top_k=top_k))

        # 3) Entities aus chunks -> Neo4j expand
        entities: List[str] = []
        for chunk in chunks:
            entities.extend(chunk.get("entities", []))
        facts = list(self.expander.expand(entities, max_facts=max_graph_facts))

        # 4) Build context: chunk texts + graph facts
        chunk_section = "\n\n".join(
            f"[chunk:{c.get('chunk_id')} score={c.get('score', 0):.4f}]\n{c.get('text', '')}" for c in chunks
        )
        graph_section = "\n".join(
            f"- ({f['entity']}) -[{f['relation']}]-> ({f['neighbor']})" for f in facts
        )

        context = (
            "### Retrieved Chunks\n"
            f"{chunk_section or 'No chunk matches found.'}\n\n"
            "### Graph Facts\n"
            f"{graph_section or 'No related graph facts found.'}"
        )

        return RetrievalResult(
            context=context,
            sources={
                "chunks": chunks,
                "graph_facts": facts,
            },
        )
