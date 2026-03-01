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


def test_document_management_lifecycle(tmp_path: Path) -> None:
    main.UPLOAD_DIR = tmp_path

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

    list_response = client.get("/documents")
    assert list_response.status_code == 200
    listed_documents = list_response.json()
    assert len(listed_documents) == 1
    assert listed_documents[0]["doc_id"] == doc_id

    get_response = client.get(f"/documents/{doc_id}")
    assert get_response.status_code == 200
    assert get_response.json()["chunk_count"] == 2

    update_response = client.put(
        f"/documents/{doc_id}",
        json={"title": "Neuer Titel", "metadata": {"owner": "backend"}},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Neuer Titel"

    delete_response = client.delete(f"/documents/{doc_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"status": "deleted", "doc_id": doc_id}

    not_found_response = client.get(f"/documents/{doc_id}")
    assert not_found_response.status_code == 404
