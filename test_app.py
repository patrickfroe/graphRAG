import sys
import types

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_graph_preview_parses_entity_keys_and_builds_edges():
    response = client.get("/graph/preview", params={"entity_keys": "ID:A,ORG:neo4j,loc-123"})

    assert response.status_code == 200
    assert response.json() == {
        "nodes": [
            {"id": "ID:A", "label": "A", "type": "entity"},
            {"id": "ORG:neo4j", "label": "neo4j", "type": "entity"},
            {"id": "loc-123", "label": "loc 123", "type": "entity"},
        ],
        "edges": [
            {"source": "ID:A", "target": "ORG:neo4j", "label": "related_to"},
            {"source": "ORG:neo4j", "target": "loc-123", "label": "related_to"},
        ],
    }


def test_graph_preview_without_keys_returns_empty_graph():
    response = client.get("/graph/preview")

    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}


def test_ingest_accepts_string_documents():
    fake_ingest = types.ModuleType("app.ingest")
    fake_ingest.ingest_documents = lambda documents: {"ingested": len(documents)}
    sys.modules["app.ingest"] = fake_ingest

    response = client.post("/ingest", json={"documents": ["one", "two"]})

    assert response.status_code == 200
    assert response.json() == {"ingested": 2}


def test_ingest_preflight_options_returns_ok():
    response = client.options(
        "/ingest",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
