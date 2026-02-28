from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from app.config import get_settings


class VectorStore:
    def __init__(self, dim: int = 1536) -> None:
        settings = get_settings()
        self.collection_name = settings.milvus_collection
        self.dim = dim

        connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)
        self.collection = self._ensure_collection()

    def _ensure_collection(self) -> Collection:
        if utility.has_collection(self.collection_name):
            collection = Collection(self.collection_name)
            collection.load()
            return collection

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
        ]
        schema = CollectionSchema(fields=fields, description="GraphRAG documents")
        collection = Collection(name=self.collection_name, schema=schema)
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
        return collection

    def upsert(self, doc_id: str, text: str, embedding: list[float]) -> None:
        self.collection.upsert(data=[[doc_id], [text], [embedding]])
        self.collection.flush()

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict]:
        result = self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            limit=top_k,
            output_fields=["text"],
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        )

        hits = []
        for hit in result[0]:
            hits.append({"id": hit.id, "score": float(hit.score), "text": hit.entity.get("text")})
        return hits

    def delete(self, doc_id: str) -> int:
        escaped_doc_id = doc_id.replace('"', '\\"')
        result = self.collection.delete(expr=f'id == "{escaped_doc_id}"')
        self.collection.flush()
        deleted_count = getattr(result, "delete_count", 0)
        return int(deleted_count)
