from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_ingest_and_chat_returns_sources() -> None:
    ingest_response = client.post(
        "/ingest", json={"documents": ["FastAPI builds APIs quickly", "GraphRAG uses retrieval"]}
    )
    assert ingest_response.status_code == 200
    assert ingest_response.json()["ingested"] == 2

    chat_response = client.post("/chat", json={"question": "What uses retrieval?"})
    assert chat_response.status_code == 200
    payload = chat_response.json()
    assert "answer" in payload
    assert isinstance(payload["sources"], list)
    assert payload["sources"]


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
