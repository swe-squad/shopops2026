from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

HEADERS = {"Authorization": "Bearer test-token"}


@pytest.mark.parametrize("token", ["", " ", "\t\n"])
def test_blank_explicit_token_fails_even_when_environment_is_configured(
    tmp_path, monkeypatch, token
):
    monkeypatch.setenv("SHOP_API_TOKEN", "environment-token")
    with pytest.raises(RuntimeError, match="SHOP_API_TOKEN"):
        with TestClient(create_app(str(tmp_path / "operations.db"), token)):
            pass


@pytest.mark.parametrize("database", ["", " \t"])
@pytest.mark.parametrize("source", ["argument", "environment"])
def test_blank_database_configuration_fails_startup(tmp_path, monkeypatch, database, source):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHOP_DATA_PATH", str(tmp_path / "environment.db"))
    if source == "environment":
        monkeypatch.setenv("SHOP_DATA_PATH", database)
    configured = database if source == "argument" else None
    with pytest.raises(RuntimeError, match="SHOP_DATA_PATH"):
        with TestClient(create_app(database=configured, token="test-token")):
            pass


@pytest.mark.parametrize("authorization", ["", "Basic test-token", "Bearer wrong", "Bearer"])
def test_invalid_bearer_tokens_cannot_read_or_mutate_operations(tmp_path, authorization):
    with TestClient(create_app(str(tmp_path / "operations.db"), "test-token")) as client:
        for path, body in [
            ("/api/operations/incidents", {"title": "Rejected"}),
            ("/api/operations/navigation", {"url": "/shop/incidents"}),
        ]:
            headers = {"Authorization": authorization}
            assert client.get(path, headers=headers).status_code == 401
            assert client.post(path, headers=headers, json=body).status_code == 401
        assert client.get("/api/operations/incidents", headers=HEADERS).json() == []
        assert client.get("/api/operations/navigation", headers=HEADERS).json() is None


def test_openapi_declares_bearer_auth_errors_and_navigation_nullability(tmp_path):
    with TestClient(create_app(str(tmp_path / "operations.db"), "test-token")) as client:
        schema = client.get("/openapi.json").json()
        assert schema["components"]["securitySchemes"]["WorkspaceToken"] == {
            "type": "http",
            "scheme": "bearer",
            "description": "Single-workspace access token.",
        }
        assert "security" not in schema["paths"]["/health"]["get"]
        for path in ["/api/operations/incidents", "/api/operations/navigation"]:
            for method in ["get", "post"]:
                route = schema["paths"][path][method]
                assert route["security"] == [{"WorkspaceToken": []}]
                assert "application/json" in route["responses"]["401"]["content"]
            assert "422" in schema["paths"][path]["post"]["responses"]
        navigation = schema["paths"]["/api/operations/navigation"]["get"]["responses"]["200"]
        assert {"type": "null"} in navigation["content"]["application/json"]["schema"]["anyOf"]


def test_concurrent_navigation_ids_and_incident_limit_survive_restart(tmp_path):
    database = str(tmp_path / "operations.db")
    with TestClient(create_app(database, "test-token")) as client:

        def navigate(index):
            response = client.post(
                "/api/operations/navigation", headers=HEADERS, json={"url": f"/shop/{index}"}
            )
            assert response.status_code == 201
            return response.json()

        with ThreadPoolExecutor(max_workers=6) as pool:
            events = list(pool.map(navigate, range(24)))
        assert len({event["id"] for event in events}) == 24
        latest = max(events, key=lambda event: event["id"])
        for index in range(105):
            response = client.post(
                "/api/operations/incidents", headers=HEADERS, json={"title": f"Item {index}"}
            )
            assert response.status_code == 201
    with TestClient(create_app(database, "test-token")) as client:
        assert client.get("/api/operations/navigation", headers=HEADERS).json() == latest
        incidents = client.get("/api/operations/incidents", headers=HEADERS).json()
        assert len(incidents) == 100
        assert incidents[0]["title"] == "Item 104"
        assert incidents[-1]["title"] == "Item 5"
