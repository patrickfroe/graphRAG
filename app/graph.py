from neo4j import GraphDatabase

from app.config import get_settings


class GraphStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self.driver.close()

    def ensure_constraints(self) -> None:
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE")
            session.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE")
            session.run(
                "CREATE CONSTRAINT entity_canonical IF NOT EXISTS FOR (e:Entity) "
                "REQUIRE e.canonical_name IS UNIQUE"
            )

    def upsert_document(self, doc_id: str, title: str, text: str) -> None:
        query = """
        MERGE (d:Document {doc_id: $doc_id})
        SET d.title = $title, d.text = $text
        """
        with self.driver.session() as session:
            session.run(query, doc_id=doc_id, title=title, text=text)

    def upsert_chunk(self, chunk_id: str, doc_id: str, text: str) -> None:
        query = """
        MERGE (d:Document {doc_id: $doc_id})
        MERGE (c:Chunk {chunk_id: $chunk_id})
        SET c.text = $text
        MERGE (d)-[:CONTAINS]->(c)
        """
        with self.driver.session() as session:
            session.run(query, chunk_id=chunk_id, doc_id=doc_id, text=text)

    def upsert_entity(self, name: str, entity_type: str, canonical_name: str, score: float) -> None:
        query = """
        MERGE (e:Entity {canonical_name: $canonical_name})
        SET e.name = $name,
            e.type = $entity_type,
            e.score = $score
        """
        with self.driver.session() as session:
            session.run(
                query,
                name=name,
                entity_type=entity_type,
                canonical_name=canonical_name,
                score=score,
            )

    def link_chunk_mentions_entity(self, chunk_id: str, canonical_name: str) -> None:
        query = """
        MATCH (c:Chunk {chunk_id: $chunk_id})
        MATCH (e:Entity {canonical_name: $canonical_name})
        MERGE (c)-[:MENTIONS]->(e)
        """
        with self.driver.session() as session:
            session.run(query, chunk_id=chunk_id, canonical_name=canonical_name)

    def link_entity_relation(self, source_canonical: str, target_canonical: str, relation: str) -> None:
        query = f"""
        MATCH (a:Entity {{canonical_name: $source_canonical}})
        MATCH (b:Entity {{canonical_name: $target_canonical}})
        MERGE (a)-[r:{relation}]->(b)
        """
        with self.driver.session() as session:
            session.run(query, source_canonical=source_canonical, target_canonical=target_canonical)

    def link_documents(self, source_id: str, target_id: str, relation: str = "RELATED_TO") -> None:
        query = f"""
        MATCH (a:Document {{doc_id: $source_id}})
        MATCH (b:Document {{doc_id: $target_id}})
        MERGE (a)-[r:{relation}]->(b)
        """
        with self.driver.session() as session:
            session.run(query, source_id=source_id, target_id=target_id)

    def list_documents(self, limit: int = 200) -> list[dict[str, str]]:
        query = """
        MATCH (d:Document)
        RETURN d.doc_id AS doc_id, d.title AS title
        ORDER BY d.doc_id ASC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [{"doc_id": record["doc_id"], "title": record["title"]} for record in result]

    def delete_document(self, doc_id: str) -> int:
        query = """
        MATCH (d:Document {doc_id: $doc_id})
        DETACH DELETE d
        RETURN COUNT(*) AS deleted_count
        """
        with self.driver.session() as session:
            record = session.run(query, doc_id=doc_id).single()
            if record is None:
                return 0
            return int(record["deleted_count"])
