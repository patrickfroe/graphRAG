from retriever import GraphRAGRetriever


class DummyEmbedder:
    def embed(self, text: str):
        assert text == "what is graph rag?"
        return [0.1, 0.2]


class DummySearcher:
    def search(self, vector, top_k: int):
        assert vector == [0.1, 0.2]
        assert top_k == 20
        return [
            {
                "chunk_id": "c1",
                "doc_id": "d1",
                "text": "GraphRAG combines vector retrieval and graph expansion.",
                "entities": ["GraphRAG", "retrieval"],
                "score": 0.95,
            },
            {
                "chunk_id": "c2",
                "doc_id": "d2",
                "text": "Neo4j stores entities and relations.",
                "entities": ["Neo4j"],
                "score": 0.90,
            },
        ]


class DummyExpander:
    def expand(self, entities, max_facts: int):
        assert set(entities) == {"GraphRAG", "retrieval", "Neo4j"}
        assert max_facts == 3
        return [
            {
                "entity": "GraphRAG",
                "relation": "USES",
                "neighbor": "Neo4j",
                "source": "kg",
            }
        ]


def test_retrieve_builds_context_and_sources():
    retriever = GraphRAGRetriever(DummyEmbedder(), DummySearcher(), DummyExpander())

    result = retriever.retrieve("what is graph rag?", top_k=2, max_graph_facts=3)

    assert "### Retrieved Chunks" in result.context
    assert "[chunk:c1 final=" in result.context
    assert "### Graph Facts" in result.context
    assert "(GraphRAG) -[USES]-> (Neo4j)" in result.context
    assert len(result.sources["chunks"]) == 2
    assert result.sources["graph_facts"][0]["entity"] == "GraphRAG"

    top_chunk = result.sources["chunks"][0]
    assert "final_score" in top_chunk
    assert "bm25_score" in top_chunk
    assert "graph_score" in top_chunk


def test_hybrid_fusion_prefers_chunk_with_better_total_score():
    retriever = GraphRAGRetriever(DummyEmbedder(), DummySearcher(), DummyExpander())

    result = retriever.retrieve("what is graph rag?", top_k=1, max_graph_facts=3)

    assert len(result.sources["chunks"]) == 1
    assert result.sources["chunks"][0]["chunk_id"] == "c1"
