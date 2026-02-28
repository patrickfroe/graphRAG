from app.mapper import retrieval_result_to_chat_response


def test_retrieval_result_to_chat_response_maps_all_fields():
    result = {
        "answer": "Kurzantwort.",
        "sources": [
            {"title": "Doc1", "url": "https://a", "score": 0.8, "snippet": "A"},
            {"title": "Doc2", "url": "https://b", "score": 0.7, "snippet": "B"},
        ],
        "entities": [
            {"name": "GraphRAG", "frequency": 2, "score": 0.5},
            {"name": "GraphRAG", "frequency": 1, "score": 0.3},
            {"name": "Neo4j", "frequency": 1, "score": 0.4},
        ],
        "graph_preview": {
            "nodes": [{"id": i} for i in range(20)],
            "edges": [{"id": i} for i in range(30)],
        },
    }

    mapped = retrieval_result_to_chat_response(result)

    assert mapped.sources[0].source_id == "S1"
    assert mapped.sources[1].source_id == "S2"
    assert "[S1]" in mapped.answer and "[S2]" in mapped.answer

    assert mapped.entities[0].name == "GraphRAG"
    assert mapped.entities[0].frequency == 3
    assert mapped.entities[0].score == 0.8
    assert mapped.entities[0].salience == 2.4

    assert len(mapped.graph_preview.nodes) == 10
    assert len(mapped.graph_preview.edges) == 20
