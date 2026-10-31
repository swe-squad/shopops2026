from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

HEADERS = {"Authorization": "Bearer test-token"}
SHOP = "shopee-open-platform:shop-one"
USER = "+84900000001"
BASE = "/api/operations/catalog"


def source_rows() -> dict[str, list[dict]]:
    shop = {
        "shop_key": SHOP,
        "name": "A shop",
        "platform": "shopee-open-platform",
        "currency": "VND",
        "timezone": "Asia/Ho_Chi_Minh",
        "merchant_id": "private-merchant",
    }
    product = {"shop_key": SHOP, "sku": "sku-a", "name": "Product A", "unit_cost": "12.50"}
    order = {
        "shop_key": SHOP,
        "order_id": "order-1",
        "ordered_at": "2026-10-28T08:00:00+07:00",
        "status": "completed",
    }
    item = {
        "shop_key": SHOP,
        "order_id": "order-1",
        "line_id": "line-1",
        "sku": "sku-a",
        "quantity": 2,
        "unit_price": "30.00",
        "status": "completed",
    }
    inventory = {
        "shop_key": SHOP,
        "sku": "sku-a",
        "location_id": "warehouse-a",
        "observed_at": "2026-10-29T08:00:00+07:00",
        "available": 5,
    }
    review = {
        "shop_key": SHOP,
        "sku": "sku-a",
        "review_id": "review-a",
        "order_id": "order-1",
        "reviewed_at": "2026-10-29T08:00:00+07:00",
        "rating": 2,
        "body": "Incorrect size",
    }
    returned = {
        "shop_key": SHOP,
        "return_id": "return-a",
        "order_id": "order-1",
        "requested_at": "2026-10-29T09:00:00+07:00",
        "reason": "Size",
        "status": "requested",
        "refund_amount": "30.00",
    }
    return {
        "shops": [shop],
        "products": [product, product | {"sku": "sku-b", "name": "Product B", "unit_cost": None}],
        "inventory": [
            inventory | {"observed_at": "2026-10-28T08:00:00+07:00", "available": 900},
            inventory,
            inventory
            | {
                "location_id": "warehouse-b",
                "observed_at": "2026-10-30T08:00:00+07:00",
                "available": 7,
            },
        ],
        "orders": [
            order,
            order
            | {
                "order_id": "cancelled",
                "ordered_at": "2026-10-31T08:00:00+07:00",
                "status": "cancelled",
            },
            order
            | {"order_id": "open", "ordered_at": "2026-10-30T08:00:00+07:00", "status": "open"},
        ],
        "order-items": [
            item,
            item | {"line_id": "line-2", "quantity": 1},
            item | {"line_id": "line-b", "sku": "sku-b"},
            item | {"order_id": "cancelled", "status": "cancelled", "unit_price": "99.00"},
            item | {"order_id": "open", "status": "open", "unit_price": "42.00"},
        ],
        "reviews": [review, review | {"review_id": "review-b", "sku": "sku-b", "rating": 5}],
        "returns": [returned],
    }


class MockSource:
    def __init__(self) -> None:
        self.rows = source_rows()
        self.revision = 7
        self.requests: list[httpx.Request] = []
        self.hook = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.headers["X-Demo-User-Id"] == USER
        assert "authorization" not in request.headers
        assert request.method == "GET"
        assert request.url.path.startswith("/v1/mock/")
        resource = request.url.path.removeprefix("/v1/mock/")
        if self.hook:
            overridden = self.hook(request, resource)
            if overridden is not None:
                return overridden
        rows = deepcopy(self.rows[resource])
        if shop_key := request.url.params.get("shop_key"):
            rows = [row for row in rows if row["shop_key"] == shop_key]
        limit, offset = int(request.url.params["limit"]), int(request.url.params["offset"])
        return httpx.Response(
            200,
            json={
                "data": rows[offset : offset + limit],
                "source_revision": self.revision,
                "pagination": {"limit": limit, "offset": offset, "total": len(rows)},
            },
        )


@pytest.fixture
def source():
    return MockSource()


@pytest.fixture
def client(tmp_path, monkeypatch, source):
    monkeypatch.setenv("SHOP_CATALOG_MODE", "source")
    monkeypatch.setenv("CRONJOB_SERVER_URL", "http://catalog.test")
    monkeypatch.setenv("SHOP_DATA_USER_ID", USER)
    app = create_app(
        str(tmp_path / "operations.db"), "test-token", catalog_transport=httpx.MockTransport(source)
    )
    with TestClient(app) as client:
        yield client


def product(client: TestClient, sku: str = "sku-a") -> httpx.Response:
    return client.get(BASE + "/product", params={"shop_key": SHOP, "sku": sku}, headers=HEADERS)
