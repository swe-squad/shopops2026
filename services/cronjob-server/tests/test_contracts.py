from fastapi.testclient import TestClient

from app.main import app


def test_openapi_exposes_mcp_headers_keys_and_typed_marts():
    schema = TestClient(app).get("/openapi.json").json()
    operation = schema["paths"]["/v1/mock/orders/record"]["patch"]
    assert {p["name"] for p in operation["parameters"]} >= {
        "X-Demo-User-Id",
        "Idempotency-Key",
        "shop_key",
        "order_id",
    }
    assert "AgentContext" in schema["components"]["schemas"]
    assert TestClient(app).get("/v1/core/invalid").json()["error"]["code"] == "NOT_FOUND"
