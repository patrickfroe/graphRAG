from app.embeddings import EmbeddingService
from app.graph import GraphStore
from app.vectorstore import VectorStore


def ingest_documents(documents: list[dict]) -> dict:
    embedding_service = EmbeddingService()
    graph_store = GraphStore()
    vector_store = VectorStore()

    graph_store.ensure_constraints()

    for doc in documents:
        doc_id = doc["id"]
        title = doc.get("title", doc_id)
        text = doc["text"]

        embedding = embedding_service.embed_text(text)
        graph_store.upsert_document(doc_id=doc_id, title=title, text=text)
        vector_store.upsert(doc_id=doc_id, text=text, embedding=embedding)

    graph_store.close()
    return {"ingested": len(documents)}
