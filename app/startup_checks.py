from __future__ import annotations

from app.config import get_settings


def test_backend_connections() -> None:
    """Fail fast if Neo4j or Milvus is not reachable at backend startup."""
    from neo4j import GraphDatabase
    from pymilvus import connections, utility

    settings = get_settings()

    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    try:
        driver.verify_connectivity()
    finally:
        driver.close()

    connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)
    utility.list_collections(timeout=3)
