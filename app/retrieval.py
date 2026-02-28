from app.config import get_settings
from app.embeddings import EmbeddingService
from app.llm import LLMService
from app.vectorstore import VectorStore


def retrieve_context(query: str, top_k: int | None = None) -> list[dict]:
    settings = get_settings()
    embedding_service = EmbeddingService()
    vector_store = VectorStore()

    query_vector = embedding_service.embed_text(query)
    return vector_store.search(query_vector, top_k=top_k or settings.top_k)


def answer_query(query: str, top_k: int | None = None) -> dict:
    llm = LLMService()
    hits = retrieve_context(query=query, top_k=top_k)
    context_chunks = [hit["text"] for hit in hits if hit.get("text")]
    answer = llm.answer(query=query, context_chunks=context_chunks)

    return {
        "query": query,
        "answer": answer,
        "sources": hits,
    }
