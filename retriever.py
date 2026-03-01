from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
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


class KeywordSearcher(Protocol):
    def search(self, query: str, chunks: Sequence[Dict[str, Any]]) -> Dict[str, float]:
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


class BM25KeywordSearcher:
    """In-memory BM25 ranker over retrieved chunks."""

    _token_pattern = re.compile(r"\b\w+\b", re.UNICODE)

    def _tokenize(self, text: str) -> List[str]:
        return [token.lower() for token in self._token_pattern.findall(text)]

    def search(self, query: str, chunks: Sequence[Dict[str, Any]]) -> Dict[str, float]:
        if not chunks:
            return {}

        docs = []
        doc_freq: Dict[str, int] = defaultdict(int)
        for chunk in chunks:
            tokens = self._tokenize(chunk.get("text", ""))
            term_counts = Counter(tokens)
            docs.append((chunk.get("chunk_id"), term_counts, len(tokens)))
            for term in term_counts:
                doc_freq[term] += 1

        avg_doc_len = sum(doc_len for _, _, doc_len in docs) / len(docs)
        query_terms = self._tokenize(query)
        if not query_terms or avg_doc_len == 0:
            return {str(chunk_id): 0.0 for chunk_id, _, _ in docs if chunk_id is not None}

        # Standard BM25 constants.
        k1 = 1.5
        b = 0.75
        total_docs = len(docs)
        scores: Dict[str, float] = {}

        for chunk_id, term_counts, doc_len in docs:
            if chunk_id is None:
                continue

            score = 0.0
            for term in query_terms:
                tf = term_counts.get(term, 0)
                if tf == 0:
                    continue
                df = doc_freq.get(term, 0)
                idf = math.log(1 + ((total_docs - df + 0.5) / (df + 0.5)))
                denom = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                score += idf * ((tf * (k1 + 1)) / denom)
            scores[str(chunk_id)] = score

        return scores


class GraphRAGRetriever:
    def __init__(
        self,
        embedder: Embedder,
        searcher: MilvusSearcher,
        expander: GraphExpander,
        keyword_searcher: KeywordSearcher | None = None,
    ) -> None:
        self.embedder = embedder
        self.searcher = searcher
        self.expander = expander
        self.keyword_searcher = keyword_searcher or BM25KeywordSearcher()

    @staticmethod
    def _min_max_normalize(scores_by_chunk: Dict[str, float]) -> Dict[str, float]:
        if not scores_by_chunk:
            return {}
        min_score = min(scores_by_chunk.values())
        max_score = max(scores_by_chunk.values())
        if math.isclose(min_score, max_score):
            return {chunk_id: 1.0 for chunk_id in scores_by_chunk}
        return {
            chunk_id: (score - min_score) / (max_score - min_score)
            for chunk_id, score in scores_by_chunk.items()
        }

    def retrieve(self, query: str, top_k: int = 5, max_graph_facts: int = 20) -> RetrievalResult:
        # 1) embed query via OpenAI
        query_vector = self.embedder.embed(query)

        # 2) Milvus search -> top chunks
        vector_chunks = list(self.searcher.search(query_vector, top_k=20))

        # 3) BM25 index over vector chunks.
        bm25_scores_raw = self.keyword_searcher.search(query, vector_chunks)

        # 4) Entities aus chunks -> Neo4j expand
        entities: List[str] = []
        for chunk in vector_chunks:
            entities.extend(chunk.get("entities", []))
        facts = list(self.expander.expand(entities, max_facts=max_graph_facts))

        # Graph score: number_of_edges_to_seed_entities.
        graph_edge_counts: Dict[str, int] = defaultdict(int)
        for fact in facts:
            seed_entity = fact.get("entity")
            if seed_entity:
                graph_edge_counts[str(seed_entity)] += 1

        graph_scores_raw: Dict[str, float] = {}
        vector_scores_raw: Dict[str, float] = {}
        for chunk in vector_chunks:
            chunk_id = str(chunk.get("chunk_id"))
            vector_scores_raw[chunk_id] = float(chunk.get("score", 0.0))
            chunk_entities = chunk.get("entities", []) or []
            graph_scores_raw[chunk_id] = float(
                sum(graph_edge_counts.get(str(entity), 0) for entity in chunk_entities)
            )

        vector_scores = self._min_max_normalize(vector_scores_raw)
        bm25_scores = self._min_max_normalize(bm25_scores_raw)
        graph_scores = self._min_max_normalize(graph_scores_raw)

        chunks: List[Dict[str, Any]] = []
        for chunk in vector_chunks:
            chunk_id = str(chunk.get("chunk_id"))
            vector_score = vector_scores.get(chunk_id, 0.0)
            bm25_score = bm25_scores.get(chunk_id, 0.0)
            graph_score = graph_scores.get(chunk_id, 0.0)
            final_score = (0.6 * vector_score) + (0.3 * bm25_score) + (0.1 * graph_score)

            merged_chunk = {
                **chunk,
                "vector_score": vector_score,
                "bm25_score": bm25_score,
                "graph_score": graph_score,
                "final_score": final_score,
            }
            chunks.append(merged_chunk)

        chunks.sort(key=lambda chunk: float(chunk.get("final_score", 0.0)), reverse=True)
        chunks = chunks[:top_k]

        # 5) Build context: chunk texts + graph facts
        chunk_section = "\n\n".join(
            (
                f"[chunk:{c.get('chunk_id')} final={c.get('final_score', 0):.4f} "
                f"vector={c.get('vector_score', 0):.4f} bm25={c.get('bm25_score', 0):.4f} "
                f"graph={c.get('graph_score', 0):.4f}]\n{c.get('text', '')}"
            )
            for c in chunks
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
