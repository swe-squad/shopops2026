from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.catalog_fixtures import BASE, HEADERS, SHOP, product


def test_authentication_precedes_source_reads(client, source):
    for path in [BASE + "/shops", BASE, BASE + "/product"]:
        for authorization in ["", "Bearer wrong", "Basic test-token"]:
            response = client.get(path, headers={"Authorization": authorization})
            assert response.status_code == 401
    assert source.requests == []


def test_shops_return_only_public_fields_and_ignore_browser_identity(client, source):
    response = client.get(
        BASE + "/shops",
        headers=HEADERS | {"X-Demo-User-Id": "+84999999999"},
        params={"user_id": "+84999999999"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_revision"] == 7
    assert datetime.fromisoformat(data["fetched_at"]).tzinfo is not None
    assert data["shops"] == [
        {
            "shop_key": SHOP,
            "name": "A shop",
            "platform": "shopee-open-platform",
            "currency": "VND",
            "timezone": "Asia/Ho_Chi_Minh",
        }
    ]
    assert source.requests[0].url.params.get("user_id") is None


def test_catalog_stock_prices_and_counts_are_derived_from_all_evidence(client, source):
    response = client.get(BASE, params={"shop_key": SHOP}, headers=HEADERS)
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot["source_revision"] == 7
    assert snapshot["data_mode"] == "mock_source"
    a, b = snapshot["products"]
    assert a == {
        "shop_key": SHOP,
        "sku": "sku-a",
        "name": "Product A",
        "image_url": None,
        "unit_cost": "12.50",
        "currency": "VND",
        "available": 12,
        "inventory_observed_at": "2026-10-29T08:00:00+07:00",
        "last_sold_price": "42.00",
        "last_sold_at": "2026-10-30T08:00:00+07:00",
        "order_count": 3,
        "review_count": 1,
        "negative_review_count": 1,
        "return_order_count": 1,
    }
    assert b["available"] is None
    assert b["inventory_observed_at"] is None
    assert b["unit_cost"] is None
    for request in source.requests:
        if not request.url.path.endswith("/shops"):
            assert request.url.params["shop_key"] == SHOP


def test_product_limits_reviews_and_lines_to_sku_and_returns_to_related_orders(client):
    data = product(client).json()
    assert [review["review_id"] for review in data["reviews"]] == ["review-a"]
    assert len(data["orders"]) == 4
    assert data["product"]["order_count"] == 3
    assert {row["return_id"] for row in data["returns"]} == {"return-a"}
    assert "sku" not in data["returns"][0]
    # A return has only an order association, and appears on both products in that order.
    b = product(client, "sku-b").json()
    assert b["returns"] == data["returns"]
    assert b["product"]["return_order_count"] == 1
    assert [review["review_id"] for review in b["reviews"]] == ["review-b"]


def test_unknown_latest_location_stock_propagates_null_instead_of_partial_sum(client, source):
    source.rows["inventory"][-1]["available"] = None
    assert product(client).json()["product"]["available"] is None


@pytest.mark.parametrize("image", [None, "https://images.example.test/product-a.webp"])
def test_optional_source_image_survives_catalog_and_product_reads(client, source, image):
    source.rows["products"][0]["image_url"] = image
    assert product(client).json()["product"]["image_url"] == image
    catalog = client.get(BASE, params={"shop_key": SHOP}, headers=HEADERS).json()
    assert catalog["products"][0]["image_url"] == image
    # Older sources omit image_url and retain the existing null placeholder contract.
    assert catalog["products"][1]["image_url"] is None


def test_zero_stock_is_known_and_no_historical_purchase_is_unknown(client, source):
    for row in source.rows["inventory"]:
        row["available"] = 0
    for row in source.rows["order-items"]:
        row["status"] = "unknown"
    data = product(client).json()["product"]
    assert data["available"] == 0
    assert data["last_sold_price"] is None
    assert data["last_sold_at"] is None


def test_hidden_shop_or_sku_returns_404_without_cross_shop_reads(client, source):
    response = client.get(BASE, params={"shop_key": "shopify:hidden"}, headers=HEADERS)
    assert response.status_code == 404
    assert all(request.url.path.endswith("/shops") for request in source.requests)
    assert product(client, "not-in-this-shop").status_code == 404


@pytest.mark.parametrize(
    "path,params",
    [
        (BASE, {}),
        (BASE, {"shop_key": ""}),
        (BASE, {"shop_key": " "}),
        (BASE, {"shop_key": "x" * 501}),
        (BASE + "/product", {"shop_key": SHOP}),
        (BASE + "/product", {"shop_key": SHOP, "sku": ""}),
        (BASE + "/product", {"shop_key": SHOP, "sku": " sku-a "}),
    ],
)
def test_invalid_selection_is_422_without_source_calls(client, source, path, params):
    assert client.get(path, params=params, headers=HEADERS).status_code == 422
    assert source.requests == []


def test_disabled_source_preserves_health_operations_and_navigation(tmp_path, monkeypatch):
    monkeypatch.delenv("SHOP_CATALOG_MODE", raising=False)
    with TestClient(create_app(str(tmp_path / "operations.db"), "test-token")) as client:
        assert client.get(BASE + "/shops").status_code == 401
        response = client.get(BASE + "/shops", headers=HEADERS)
        assert response.status_code == 503
        assert set(response.json()) == {"detail"}
        assert client.get("/health").status_code == 200
        assert client.get("/api/operations/incidents", headers=HEADERS).json() == []
        assert client.get("/api/operations/navigation", headers=HEADERS).json() is None


def test_catalog_openapi_declares_auth_dtos_and_failure_responses(client):
    schema = client.get("/openapi.json").json()
    for path in [BASE, BASE + "/shops", BASE + "/product"]:
        route = schema["paths"][path]["get"]
        assert route["security"] == [{"WorkspaceToken": []}]
        assert {"200", "401", "404", "503"} <= set(route["responses"])
