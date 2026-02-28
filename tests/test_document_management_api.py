import importlib
import sys
import types

from fastapi.testclient import TestClient


def test_documents_list_and_delete() -> None:
    fake_ingest = types.ModuleType("app.ingest")
    fake_ingest.ingest_documents = lambda documents: {"ingested": len(documents)}
    fake_ingest.list_ingested_documents = lambda limit=200: [
        {"doc_id": "doc-1", "title": "Dokument 1"},
        {"doc_id": "doc-2", "title": "Dokument 2"},
    ]
    fake_ingest.delete_ingested_document = lambda doc_id: {"graph_deleted": 1, "vector_deleted": 1}

    fake_retrieval = types.ModuleType("app.retrieval")
    fake_retrieval.answer_query = lambda query, top_k=None: {"answer": query, "sources": []}

    fake_startup_checks = types.ModuleType("app.startup_checks")
    fake_startup_checks.test_backend_connections = lambda: None

    sys.modules["app.ingest"] = fake_ingest
    sys.modules["app.retrieval"] = fake_retrieval
    sys.modules["app.startup_checks"] = fake_startup_checks

    api_module = importlib.import_module("app.api")
    api_module = importlib.reload(api_module)

    client = TestClient(api_module.app)

    list_response = client.get("/documents")
    assert list_response.status_code == 200
    assert list_response.json() == {
        "documents": [
            {"doc_id": "doc-1", "title": "Dokument 1"},
            {"doc_id": "doc-2", "title": "Dokument 2"},
        ]
    }

    delete_response = client.delete("/documents/doc-1")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True, "graph_deleted": 1, "vector_deleted": 1}


def test_delete_returns_404_when_document_does_not_exist() -> None:
    fake_ingest = types.ModuleType("app.ingest")
    fake_ingest.ingest_documents = lambda documents: {"ingested": len(documents)}
    fake_ingest.list_ingested_documents = lambda limit=200: []
    fake_ingest.delete_ingested_document = lambda doc_id: {"graph_deleted": 0, "vector_deleted": 0}

    fake_retrieval = types.ModuleType("app.retrieval")
    fake_retrieval.answer_query = lambda query, top_k=None: {"answer": query, "sources": []}

    fake_startup_checks = types.ModuleType("app.startup_checks")
    fake_startup_checks.test_backend_connections = lambda: None

    sys.modules["app.ingest"] = fake_ingest
    sys.modules["app.retrieval"] = fake_retrieval
    sys.modules["app.startup_checks"] = fake_startup_checks

    api_module = importlib.import_module("app.api")
    api_module = importlib.reload(api_module)

    client = TestClient(api_module.app)

    delete_response = client.delete("/documents/not-there")
    assert delete_response.status_code == 404
    assert delete_response.json()["detail"] == "Document 'not-there' was not found"
