import importlib
import sys
import types

from fastapi.testclient import TestClient



def test_ingest_preflight_options_returns_ok() -> None:
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
