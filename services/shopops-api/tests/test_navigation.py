import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

HEADERS = {"Authorization": "Bearer test-token"}


def test_navigation_requires_auth_and_persists_only_latest_event_with_increasing_id(tmp_path):
    path = str(tmp_path / "operations.db")
    with TestClient(create_app(path, "test-token")) as client:
        assert client.get("/api/operations/navigation").status_code == 401
        assert (
            client.post("/api/operations/navigation", json={"url": "/shop/one"}).status_code == 401
        )
        assert client.get("/api/operations/navigation", headers=HEADERS).json() is None
        first = client.post(
            "/api/operations/navigation", headers=HEADERS, json={"url": "/shop/one"}
        )
        assert first.status_code == 201
    with TestClient(create_app(path, "test-token")) as client:
        assert client.get("/api/operations/navigation", headers=HEADERS).json() == first.json()
        second = client.post(
            "/api/operations/navigation",
            headers=HEADERS,
            json={"url": "https://example.com/product?sku=1#details"},
        ).json()
        assert second["id"] > first.json()["id"]
        third = client.post(
            "/api/operations/navigation", headers=HEADERS, json={"url": "/shop/two"}
        ).json()
        assert third["id"] > second["id"]
        assert client.get("/api/operations/navigation", headers=HEADERS).json() == third
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM navigation").fetchone()[0] == 1


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,x",
        "//example.com",
        "https://user:pass@example.com",
        "https://",
        "relative/path",
        "/other/path",
        "/shopper",
        "https://example.com\n/path",
        "https://example.com:99999",
        "https://example.com\\path",
        " https://example.com",
        "/shop/\tunsafe",
        "file:///etc/passwd",
        "https://example.com/\u0080control",
    ],
)
def test_navigation_rejects_unsafe_urls(tmp_path, url):
    with TestClient(create_app(str(tmp_path / "db"), "test-token")) as client:
        assert (
            client.post(
                "/api/operations/navigation", headers=HEADERS, json={"url": url}
            ).status_code
            == 422
        )
        assert client.get("/api/operations/navigation", headers=HEADERS).json() is None
