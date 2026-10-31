import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_operations_are_authenticated_and_persistent_and_legacy_chat_is_preserved(tmp_path):
    database = str(tmp_path / "shop.db")
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, text TEXT)")
        db.execute("INSERT INTO messages(text) VALUES('existing message')")
    with TestClient(create_app(database, "test-token")) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/chat/messages").status_code == 404
        assert client.get("/api/operations/incidents").status_code == 401
        headers = {"Authorization": "Bearer test-token"}
        assert (
            client.post(
                "/api/operations/incidents", json={"title": "  "}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/operations/incidents", json={"title": "Stock low"}, headers=headers
            ).status_code
            == 201
        )
    with TestClient(create_app(database, "test-token")) as client:
        headers = {"Authorization": "Bearer test-token"}
        assert (
            client.get("/api/operations/incidents", headers=headers).json()[0]["title"]
            == "Stock low"
        )
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT text FROM messages").fetchone()[0] == "existing message"


def test_missing_token_fails_startup(tmp_path, monkeypatch):
    monkeypatch.delenv("SHOP_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="SHOP_API_TOKEN"):
        with TestClient(create_app(str(tmp_path / "data.db"))):
            pass
