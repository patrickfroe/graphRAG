from pathlib import Path

from fastapi.testclient import TestClient

import main
from main import CHUNK_STORE, DOCUMENT_METADATA, DOCUMENT_STORE, VECTOR_STORE, app


client = TestClient(app)


def setup_function() -> None:
    VECTOR_STORE.clear()
    DOCUMENT_STORE.clear()
    CHUNK_STORE.clear()
    DOCUMENT_METADATA.clear()


def test_ingest_and_chat_returns_sources() -> None:
    ingest_response = client.post(
        "/ingest", json={"documents": ["FastAPI builds APIs quickly", "GraphRAG uses retrieval"]}
    )
    assert ingest_response.status_code == 200
    assert ingest_response.json()["ingested"] == 2

    chat_response = client.post(
        "/chat",
        json={
            "query": "What uses retrieval?",
            "top_k": 8,
            "graph_hops": 2,
            "use_graph": True,
            "use_vector": True,
            "return_debug": True,
        },
    )
    assert chat_response.status_code == 200
    payload = chat_response.json()
    assert "answer" in payload
    assert isinstance(payload["citations"], list)
    assert isinstance(payload["sources"], list)
    assert payload["sources"]
    assert "source_id" in payload["sources"][0]
    assert payload["graph_evidence"]["seed_entity_keys"]
    assert payload["graph_evidence"]["preview"]["nodes"]


def test_ingest_accepts_utf8_txt_upload() -> None:
    ingest_response = client.post(
        "/ingest",
        files={"files": ("example.txt", "Ein Testdokument für den Upload", "text/plain")},
    )

    assert ingest_response.status_code == 200
    assert ingest_response.json()["ingested"] == 1


def test_ingest_accepts_object_documents() -> None:
    ingest_response = client.post(
        "/ingest",
        json={
            "documents": [
                {"id": "upload-1", "text": "AutoSys AG baut Plattformen"},
                {"id": "upload-2", "content": "GraphRAG unterstützt Quellenangaben"},
            ]
        },
    )

    assert ingest_response.status_code == 200
    assert ingest_response.json()["ingested"] == 2




def test_ingest_extracts_person_and_company_entities() -> None:
    ingest_response = client.post(
        "/ingest",
        json={
            "documents": ["Alice Johnson met with Acme GmbH leadership"],
            "entity_candidates": ["person", "company"],
        },
    )

    assert ingest_response.status_code == 200
    assert ingest_response.json()["ingested"] == 1
    assert VECTOR_STORE
    extracted = VECTOR_STORE[0].entities
    assert any(entity["type"] == "person" and entity["name"] == "Alice Johnson" for entity in extracted)
    assert any(entity["type"] == "company" and entity["name"] == "Acme GmbH" for entity in extracted)


def test_chat_returns_detected_entities() -> None:
    client.post(
        "/ingest",
        json={
            "documents": ["Alice Johnson met with Acme GmbH leadership"],
            "entity_candidates": ["person", "company"],
        },
    )

    chat_response = client.post("/chat", json={"query": "Acme GmbH", "top_k": 1})

    assert chat_response.status_code == 200
    entities = chat_response.json()["entities"]
    assert any(entity["type"] == "company" and entity["name"] == "Acme GmbH" for entity in entities)
def test_graph_preview_and_evidence_endpoints() -> None:
    ingest_response = client.post(
        "/ingest",
        json={"documents": ["Alpha and Beta are related", "Gamma references Delta"]},
    )
    assert ingest_response.status_code == 200

    graph_response = client.get(
        "/graph/preview",
        params={"entity_keys": "Alpha,Beta,Gamma", "max_nodes": 2, "max_edges": 1},
    )
    assert graph_response.status_code == 200
    assert graph_response.json() == {
        "nodes": [
            {"id": "Alpha", "label": "Alpha", "type": "entity"},
            {"id": "Beta", "label": "Beta", "type": "entity"},
        ],
        "edges": [{"source": "Alpha", "target": "Beta", "label": "related_to"}],
    }

    evidence_response = client.get("/evidence", params={"chunk_ids": "1"})
    assert evidence_response.status_code == 200
    assert evidence_response.json() == {
        "chunks": [
            {
                "chunk_id": "1",
                "doc_id": "doc-1",
                "title": "doc-1",
                "text": "Alpha and Beta are related",
            }
        ]
    }



def test_graph_document_returns_limited_graph_preview(monkeypatch) -> None:
    monkeypatch.setattr(main, "NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setattr(main, "NEO4J_USER", "neo4j")
    monkeypatch.setattr(main, "NEO4J_PASSWORD", "secret")

    class FakeNode:
        def __init__(self, node_id: int, name: str, label: str = "Entity") -> None:
            self.id = node_id
            self.labels = {label}
            self._props = {"name": name}

        def get(self, key: str):
            return self._props.get(key)

    class FakeRecord(dict):
        pass

    record = FakeRecord(
        entities=[FakeNode(1, "Entity 1"), FakeNode(2, "Entity 2")],
        neighbors=[FakeNode(3, "Neighbor 3"), FakeNode(4, "Neighbor 4")],
        raw_edges=[
            {"source": "1", "target": "2", "label": "REL_12"},
            {"source": "2", "target": "3", "label": "REL_23"},
            {"source": "3", "target": "999", "label": "REL_INVALID"},
        ],
    )

    class FakeResult:
        def single(self):
            return record

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def run(self, _query: str, **_kwargs):
            return FakeResult()

    class FakeDriver:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def session(self):
            return FakeSession()

    monkeypatch.setattr(main.GraphDatabase, "driver", lambda *_args, **_kwargs: FakeDriver())
    monkeypatch.setattr(main, "GRAPH_DOCUMENT_MAX_NODES", 3)
    monkeypatch.setattr(main, "GRAPH_DOCUMENT_MAX_EDGES", 2)

    response = client.get("/graph/document/doc-1")

    assert response.status_code == 200
    assert response.json() == {
        "nodes": [
            {"id": "1", "label": "Entity 1", "type": "entity"},
            {"id": "2", "label": "Entity 2", "type": "entity"},
            {"id": "3", "label": "Neighbor 3", "type": "entity"},
        ],
        "edges": [
            {"source": "1", "target": "2", "label": "REL_12"},
            {"source": "2", "target": "3", "label": "REL_23"},
        ],
    }




def test_graph_document_all_returns_cross_document_graph(monkeypatch) -> None:
    monkeypatch.setattr(main, "NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setattr(main, "NEO4J_USER", "neo4j")
    monkeypatch.setattr(main, "NEO4J_PASSWORD", "secret")

    class FakeNode:
        def __init__(self, node_id: int, name: str, label: str = "Entity") -> None:
            self.id = node_id
            self.labels = {label}
            self._props = {"name": name}

        def get(self, key: str):
            return self._props.get(key)

    class FakeRecord(dict):
        pass

    record = FakeRecord(
        entities=[FakeNode(1, "Entity 1"), FakeNode(2, "Entity 2")],
        neighbors=[FakeNode(3, "Neighbor 3")],
        raw_edges=[
            {"source": "1", "target": "2", "label": "REL_12"},
            {"source": "2", "target": "3", "label": "REL_23"},
        ],
    )

    captured_params: dict[str, str] = {}

    class FakeResult:
        def single(self):
            return record

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def run(self, _query: str, **kwargs):
            captured_params.update(kwargs)
            return FakeResult()

    class FakeDriver:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def session(self):
            return FakeSession()

    monkeypatch.setattr(main.GraphDatabase, "driver", lambda *_args, **_kwargs: FakeDriver())

    response = client.get("/graph/document/all")

    assert response.status_code == 200
    assert captured_params == {}
    assert response.json()["nodes"]
    assert response.json()["edges"]
def test_graph_document_requires_neo4j_configuration(monkeypatch) -> None:
    monkeypatch.setattr(main, "NEO4J_URI", None)
    monkeypatch.setattr(main, "NEO4J_USER", None)
    monkeypatch.setattr(main, "NEO4J_PASSWORD", None)

    response = client.get("/graph/document/doc-1")

    assert response.status_code == 500
    assert response.json() == {"detail": "Neo4j configuration is missing"}


def test_chunk_size_is_configurable(monkeypatch) -> None:
    monkeypatch.setattr(main, "CHUNK_SIZE", 10)

    chunks = main._chunk_text("eins zwei drei vier")

    assert chunks == ["eins zwei", "drei vier"]

def test_document_management_lifecycle(tmp_path: Path, monkeypatch) -> None:
    main.UPLOAD_DIR = tmp_path
    monkeypatch.setattr(main, "CHUNK_MIN_CHARS", 1)

    upload_response = client.post(
        "/documents/upload",
        files={"file": ("report.txt", "Erster Absatz\n\nZweiter Absatz", "text/plain")},
    )
    assert upload_response.status_code == 200
    document = upload_response.json()
    doc_id = document["doc_id"]
    assert document["title"] == "report"
    assert document["file_name"] == "report.txt"
    assert document["chunk_count"] == 2
    assert document["extracted_entity_count"] >= 0
    assert isinstance(document["extracted_entities"], list)

    list_response = client.get("/documents")
    assert list_response.status_code == 200
    listed_documents = list_response.json()
    assert len(listed_documents) == 1
    assert listed_documents[0]["doc_id"] == doc_id

    get_response = client.get(f"/documents/{doc_id}")
    assert get_response.status_code == 200
    assert get_response.json()["chunk_count"] == 2
    assert "extracted_entities" in get_response.json()

    update_response = client.put(
        f"/documents/{doc_id}",
        json={"title": "Neuer Titel", "metadata": {"owner": "backend"}},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Neuer Titel"

    reindex_response = client.post(f"/documents/{doc_id}/reindex")
    assert reindex_response.status_code == 200
    assert reindex_response.json() == {"reindexed": True, "doc_id": doc_id, "chunk_count": 2}

    delete_response = client.delete(f"/documents/{doc_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "deleted", "doc_id": doc_id}

    not_found_response = client.get(f"/documents/{doc_id}")
    assert not_found_response.status_code == 404


def test_chunk_paragraphs_toggle_is_configurable(monkeypatch) -> None:
    monkeypatch.setattr(main, "CHUNK_SIZE", 50)
    monkeypatch.setattr(main, "CHUNK_PARAGRAPHS_ENABLED", False)
    monkeypatch.setattr(main, "CHUNK_BULLET_LISTS_ENABLED", True)
    monkeypatch.setattr(main, "CHUNK_MIN_CHARS", 1)

    chunks = main._chunk_text("Erster Absatz\n\nZweiter Absatz")

    assert chunks == ["Erster Absatz\n\nZweiter Absatz"]


def test_chunk_bullet_lists_toggle_is_configurable(monkeypatch) -> None:
    monkeypatch.setattr(main, "CHUNK_SIZE", 30)
    monkeypatch.setattr(main, "CHUNK_PARAGRAPHS_ENABLED", True)
    monkeypatch.setattr(main, "CHUNK_BULLET_LISTS_ENABLED", False)
    monkeypatch.setattr(main, "CHUNK_MIN_CHARS", 1)

    chunks = main._chunk_text("Einleitung\n\n- Punkt eins\n- Punkt zwei")

    assert chunks == ["Einleitung", "- Punkt eins\n- Punkt zwei"]


def test_chunk_min_chars_is_configurable(monkeypatch) -> None:
    monkeypatch.setattr(main, "CHUNK_SIZE", 100)
    monkeypatch.setattr(main, "CHUNK_PARAGRAPHS_ENABLED", True)
    monkeypatch.setattr(main, "CHUNK_BULLET_LISTS_ENABLED", True)
    monkeypatch.setattr(main, "CHUNK_MIN_CHARS", 20)

    chunks = main._chunk_text("Kurz\n\nDieser Absatz ist ausreichend lang")

    assert chunks == ["Kurz\n\nDieser Absatz ist ausreichend lang"]
