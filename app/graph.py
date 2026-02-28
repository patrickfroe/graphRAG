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

    def upsert_document(self, doc_id: str, title: str, text: str) -> None:
        query = """
        MERGE (d:Document {doc_id: $doc_id})
        SET d.title = $title, d.text = $text
        """
        with self.driver.session() as session:
            session.run(query, doc_id=doc_id, title=title, text=text)

    def link_documents(self, source_id: str, target_id: str, relation: str = "RELATED_TO") -> None:
        query = f"""
        MATCH (a:Document {{doc_id: $source_id}})
        MATCH (b:Document {{doc_id: $target_id}})
        MERGE (a)-[r:{relation}]->(b)
        """
        with self.driver.session() as session:
            session.run(query, source_id=source_id, target_id=target_id)
