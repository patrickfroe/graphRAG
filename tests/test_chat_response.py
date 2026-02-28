from backend.chat_response import build_chat_response


def test_build_chat_response_core_fields():
    result = {
        "answer": "chunk-1 discusses Alice and doc-7 links to Bob.",
        "retrieved_chunks": [
            {
                "chunk_id": "chunk-1",
                "doc_id": "doc-7",
                "snippet": "Alice knows Bob",
                "score": 0.9,
                "entities": ["Alice", "Bob"],
            },
            {
                "chunk_id": "chunk-2",
                "doc_id": "doc-8",
                "text": "Alice works at ACME",
                "score": 0.6,
                "entities": [{"name": "Alice"}, {"key": "ACME"}],
            },
        ],
        "graph": {
            "nodes": [{"id": "n1", "label": "Alice"}, {"id": "n2", "label": "Bob"}],
            "edges": [{"source": "n1", "target": "n2", "type": "KNOWS"}],
        },
        "top_k": 2,
        "hops": 1,
    }

    response = build_chat_response(result)

    assert response.sources[0].source_id == "S1"
    assert response.sources[1].source_id == "S2"
    assert "[S1]" in response.answer
    assert len(response.entities) == 3
    assert response.entities[0].key.lower() == "alice"
    assert response.trace.top_k == 2
    assert response.trace.hops == 1
    assert response.trace.graph_nodes == 2
    assert response.trace.graph_edges == 1
