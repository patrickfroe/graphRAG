import sys
import types

from app import startup_checks


class FakeDriver:
    def __init__(self) -> None:
        self.verified = False
        self.closed = False

    def verify_connectivity(self) -> None:
        self.verified = True

    def close(self) -> None:
        self.closed = True


def test_backend_connections_checks_neo4j_and_milvus(monkeypatch) -> None:
    fake_driver = FakeDriver()
    called: dict[str, object] = {}

    neo4j_module = types.ModuleType("neo4j")

    class FakeGraphDatabase:
        @staticmethod
        def driver(uri, auth):
            called["uri"] = uri
            called["auth"] = auth
            return fake_driver

    neo4j_module.GraphDatabase = FakeGraphDatabase

    pymilvus_module = types.ModuleType("pymilvus")

    class FakeConnections:
        @staticmethod
        def connect(alias, host, port):
            called["milvus_connect"] = {"alias": alias, "host": host, "port": port}

    class FakeUtility:
        @staticmethod
        def list_collections(timeout):
            called["list_collections_timeout"] = timeout
            return []

    pymilvus_module.connections = FakeConnections
    pymilvus_module.utility = FakeUtility

    monkeypatch.setitem(sys.modules, "neo4j", neo4j_module)
    monkeypatch.setitem(sys.modules, "pymilvus", pymilvus_module)

    startup_checks.test_backend_connections()

    assert fake_driver.verified is True
    assert fake_driver.closed is True
    assert called["uri"]
    assert called["auth"]
    assert called["milvus_connect"]
    assert called["list_collections_timeout"] == 3
