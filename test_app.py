from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_graph_preview_parses_entity_keys_and_builds_edges():
    response = client.get("/graph/preview", params={"entity_keys": "A,B,C"})

    assert response.status_code == 200
    assert response.json() == {
        "nodes": [
            {"id": "A", "label": "A", "type": "entity"},
            {"id": "B", "label": "B", "type": "entity"},
            {"id": "C", "label": "C", "type": "entity"},
        ],
        "edges": [
            {"source": "A", "target": "B", "label": "related_to"},
            {"source": "B", "target": "C", "label": "related_to"},
        ],
    }


def test_graph_preview_without_keys_returns_empty_graph():
    response = client.get("/graph/preview")

    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}
