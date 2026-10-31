"""CRUD contract and authorization checks through the real MCP SDK."""

import asyncio
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.auth import Identity
from app.service import DataService
from app.settings import Settings, Shop
from tests.test_protocol import sdk_session, tool_payload

SHOP_RESOURCES = {
    "inventory",
    "settlements",
    "fulfillment",
    "account_health",
    "reviews",
    "returns",
    "orders",
    "order_items",
    "products",
    "promotions",
    "shops",
}
ADMIN_RESOURCES = {"users", "merchants", "merchant_memberships"}
PHONE = "+84900000001"
RUN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        control_dsn="postgresql://control@localhost/test",
        membership_dsn="postgresql://membership@localhost/test",
        public_url="https://mcp.example/mcp",
        shops={"shop-a": Shop(query_dsn="postgresql://shop@localhost/test", datasets=[])},
    )


def identity(*scopes: str) -> Identity:
    return Identity(subject=PHONE, shops={"shop-a"}, scopes={"data:read", *scopes})


def test_all_crud_tools_have_typed_schemas_and_annotations(settings):
    async def exercise():
        async with sdk_session(DataService(settings)) as session:
            listed = {t.name: t for t in (await session.list_tools()).tools}
            for resource in SHOP_RESOURCES | ADMIN_RESOURCES:
                for action in ("list", "get", "create", "update", "delete"):
                    tool = listed[f"cronjob_{action}_{resource}"]
                    assert tool.annotations.read_only_hint == (action in {"list", "get"})
                    assert tool.annotations.destructive_hint == (action in {"update", "delete"})
                    props = tool.input_schema["properties"]
                    assert "phone" not in props and "url" not in props
                    if action in {"create", "update", "delete"}:
                        assert "idempotency_key" in tool.input_schema["required"]
                    if action in {"create", "update"}:
                        assert "data" in props
                        assert "$ref" in props["data"] or "properties" in props["data"]
            assert "cronjob_get_sync_run" in listed

    asyncio.run(exercise())


def test_product_crud_forwards_identity_keys_payload_and_receipt(settings):
    from app.cronjob import CronjobUpstream

    calls = []
    product = {
        "shop_key": "shop-a",
        "sku": "sku/a+1",
        "name": "Tea",
        "unit_cost": "2.50",
        "cost_basis": "purchase",
    }

    def handle(request):
        calls.append(request)
        assert request.headers["X-Demo-User-Id"] == PHONE
        assert request.url.host == "cronjob.internal"
        if request.method == "GET":
            assert "Idempotency-Key" not in request.headers
            if request.url.path.endswith("/record"):
                assert dict(request.url.params) == {"shop_key": "shop-a", "sku": "sku/a+1"}
                return httpx.Response(200, json={"data": product, "source_revision": 2})
            assert dict(request.url.params) == {"shop_key": "shop-a", "limit": "10", "offset": "0"}
            return httpx.Response(
                200,
                json={
                    "data": [product],
                    "source_revision": 2,
                    "pagination": {"limit": 10, "offset": 0, "total": 1},
                },
            )
        assert request.headers["Idempotency-Key"] == "intent-1"
        if request.method == "POST":
            assert not request.url.query
            assert json.loads(request.content) == product
        else:
            assert dict(request.url.params) == {"shop_key": "shop-a", "sku": "sku/a+1"}
            if request.method == "PATCH":
                assert json.loads(request.content) == {"unit_cost": None}
        return httpx.Response(
            202,
            json={
                "data": None,
                "source_revision": None,
                "mutation_status": "unknown",
                "run_id": RUN_ID,
                "sync_status": "queued",
                "status_url": f"/v1/sync-runs/{RUN_ID}",
            },
        )

    service = DataService(settings)
    service.cronjob = CronjobUpstream(
        "http://cronjob.internal", "service", transport=httpx.MockTransport(handle)
    )

    async def exercise():
        async with sdk_session(service, identity("cronjob:read", "cronjob:write")) as session:
            cases = [
                ("list", {"shop_key": "shop-a", "limit": 10}),
                ("get", {"key": {"shop_key": "shop-a", "sku": "sku/a+1"}}),
                ("create", {"data": product, "idempotency_key": "intent-1"}),
                (
                    "update",
                    {
                        "key": {"shop_key": "shop-a", "sku": "sku/a+1"},
                        "data": {"unit_cost": None},
                        "idempotency_key": "intent-1",
                    },
                ),
                (
                    "delete",
                    {
                        "key": {"shop_key": "shop-a", "sku": "sku/a+1"},
                        "idempotency_key": "intent-1",
                    },
                ),
            ]
            for action, args in cases:
                result = await session.call_tool(f"cronjob_{action}_products", args)
                assert not result.is_error, result
                if action in {"create", "update", "delete"}:
                    assert tool_payload(result)["mutation_status"] == "unknown"
                    assert tool_payload(result)["run_id"] == RUN_ID

    asyncio.run(exercise())
    assert [r.method for r in calls] == ["GET", "GET", "POST", "PATCH", "DELETE"]


@pytest.mark.parametrize(
    "tool,args,scopes",
    [
        ("cronjob_list_products", {}, ()),
        ("cronjob_list_products", {"shop_key": "other"}, ("cronjob:read",)),
        ("cronjob_list_users", {}, ("cronjob:read",)),
        (
            "cronjob_delete_products",
            {"key": {"shop_key": "shop-a", "sku": "a"}, "idempotency_key": "x"},
            ("cronjob:read",),
        ),
        (
            "cronjob_update_products",
            {
                "key": {"shop_key": "other", "sku": "a"},
                "data": {"name": "new"},
                "idempotency_key": "x",
            },
            ("cronjob:write",),
        ),
        (
            "cronjob_update_products",
            {
                "key": {"shop_key": "shop-a", "sku": "a"},
                "data": {"shop_key": "other"},
                "idempotency_key": "x",
            },
            ("cronjob:write",),
        ),
        (
            "cronjob_update_products",
            {"key": {"shop_key": "shop-a", "sku": "a"}, "data": {}, "idempotency_key": "x"},
            ("cronjob:write",),
        ),
        (
            "cronjob_delete_products",
            {"key": {"shop_key": "shop-a", "sku": "a"}, "idempotency_key": "x\r\nInjected: yes"},
            ("cronjob:write",),
        ),
        ("cronjob_list_products", {"limit": 1001}, ("cronjob:read",)),
    ],
)
def test_invalid_or_unauthorized_calls_never_reach_cronjob(settings, tool, args, scopes):
    service = DataService(settings)
    service.cronjob = AsyncMock()

    async def exercise():
        async with sdk_session(service, identity(*scopes)) as session:
            assert (await session.call_tool(tool, args)).is_error

    asyncio.run(exercise())
    service.cronjob.request.assert_not_awaited()


def receipt(data=None, *, admin=False):
    return {
        "data": data,
        "source_revision": 2,
        "mutation_status": "applied",
        "run_id": RUN_ID,
        "sync_status": "queued",
        "status_url": f"/v1/{'admin/' if admin else ''}sync-runs/{RUN_ID}",
    }


# Examples from the provider's facade contract, independent of the registration table.
COMMON = {"shop_key": "shop-a"}
TIME = "2026-10-01T00:00:00Z"
LATER = "2026-10-02T00:00:00Z"
RESOURCE_CASES = [
    (
        "inventory",
        {**COMMON, "sku": "tea", "location_id": "store", "observed_at": TIME, "available": 3},
        ("shop_key", "sku", "location_id", "observed_at"),
        {"available": 0},
    ),
    (
        "settlements",
        {
            **COMMON,
            "order_id": "order-1",
            "fee_amount": None,
            "seller_shipping_cost": None,
            "refund_amount": None,
            "actual_payout": "-2.00",
            "paid_at": None,
        },
        ("shop_key", "order_id"),
        {"fee_amount": "1.00"},
    ),
    (
        "fulfillment",
        {
            **COMMON,
            "order_id": "order-1",
            "ship_by": LATER,
            "shipped_at": None,
            "deadline_basis": "platform",
        },
        ("shop_key", "order_id"),
        {"shipped_at": TIME},
    ),
    (
        "account-health",
        {
            **COMMON,
            "event_id": "event-1",
            "occurred_at": TIME,
            "expires_at": LATER,
            "penalty_points": 2,
            "reason": "late",
        },
        ("shop_key", "event_id"),
        {"penalty_points": 1},
    ),
    (
        "reviews",
        {
            **COMMON,
            "review_id": "review-1",
            "order_id": "order-1",
            "sku": "tea",
            "reviewed_at": TIME,
            "rating": 4,
            "body": "Good",
        },
        ("shop_key", "review_id"),
        {"rating": 5},
    ),
    (
        "returns",
        {
            **COMMON,
            "return_id": "return-1",
            "order_id": "order-1",
            "requested_at": TIME,
            "reason": "damaged",
            "status": "open",
            "refund_amount": "2.00",
        },
        ("shop_key", "return_id"),
        {"status": "closed"},
    ),
    (
        "orders",
        {
            **COMMON,
            "order_id": "order-1",
            "ordered_at": TIME,
            "updated_at": LATER,
            "currency": "USD",
            "status": "open",
            "original_status": "NEW",
            "seller_discount": None,
            "platform_discount": None,
            "promotion_id": None,
        },
        ("shop_key", "order_id"),
        {"status": "completed"},
    ),
    (
        "order-items",
        {
            **COMMON,
            "order_id": "order-1",
            "line_id": "line-1",
            "sku": "tea",
            "quantity": 2,
            "unit_price": "2.00",
            "status": "open",
            "native_status": None,
        },
        ("shop_key", "order_id", "line_id"),
        {"quantity": 3},
    ),
    (
        "products",
        {**COMMON, "sku": "tea", "name": "Tea", "unit_cost": "2.00", "cost_basis": "purchase"},
        ("shop_key", "sku"),
        {"name": "Green tea"},
    ),
    (
        "promotions",
        {
            **COMMON,
            "promotion_id": "promotion-1",
            "name": "Sale",
            "funding": "seller",
            "starts_at": TIME,
            "ends_at": LATER,
        },
        ("shop_key", "promotion_id"),
        {"name": "New sale"},
    ),
    (
        "shops",
        {
            "shop_key": "shopify:store",
            "merchant_id": "merchant-1",
            "platform": "shopify",
            "source_shop_id": "store",
            "name": "Store",
            "currency": "USD",
            "timezone": "UTC",
            "capabilities": {},
        },
        ("shop_key",),
        {"name": "New store"},
    ),
    (
        "users",
        {"user_id": PHONE, "display_name": "Demo", "is_active": True},
        ("user_id",),
        {"is_active": False},
    ),
    (
        "merchants",
        {"merchant_id": "merchant-1", "name": "Merchant", "is_active": True},
        ("merchant_id",),
        {"name": "New merchant"},
    ),
    (
        "merchant-memberships",
        {"user_id": PHONE, "merchant_id": "merchant-1", "role": "analyst", "is_active": True},
        ("user_id", "merchant_id"),
        {"role": "viewer"},
    ),
]


def test_all_70_routes_forward_the_contract_and_validate_responses(settings):
    from app.cronjob import CronjobUpstream

    expected = {}
    calls = []

    def handle(request):
        calls.append(request)
        assert request.method == expected["method"]
        assert request.url.path == expected["path"]
        assert dict(request.url.params) == expected["params"]
        assert request.headers["X-Demo-User-Id"] == PHONE
        if request.method in {"POST", "PATCH"}:
            assert json.loads(request.content) == expected["body"]
        if request.method != "GET":
            assert request.headers["Idempotency-Key"] == "one-intent"
        return httpx.Response(200 if request.method == "GET" else 202, json=expected["response"])

    settings.cronjob_admin_phones = {PHONE}
    service = DataService(settings)
    service.cronjob = CronjobUpstream(
        "http://cronjob.internal", "service", transport=httpx.MockTransport(handle)
    )
    who = identity("cronjob:read", "cronjob:write")
    who.shops.add("shopify:store")

    async def exercise():
        async with sdk_session(service, who) as session:
            for name, record, keys, patch in RESOURCE_CASES:
                admin = name.replace("-", "_") in ADMIN_RESOURCES
                path = f"/v1/{'admin/' if admin else ''}mock/{name}"
                key = {k: record[k] for k in keys}
                list_args = {} if admin else {"shop_key": record["shop_key"]}
                for action, method, args, body in [
                    ("list", "GET", list_args, None),
                    ("get", "GET", {"key": key}, None),
                    ("create", "POST", {"data": record, "idempotency_key": "one-intent"}, record),
                    (
                        "update",
                        "PATCH",
                        {"key": key, "data": patch, "idempotency_key": "one-intent"},
                        patch,
                    ),
                    ("delete", "DELETE", {"key": key, "idempotency_key": "one-intent"}, None),
                ]:
                    result_record = {**record, **(patch if action == "update" else {})}
                    response = receipt(
                        result_record if action != "delete" else {"deleted": True}, admin=admin
                    )
                    if action == "list":
                        response = {
                            "data": [record],
                            "source_revision": 2,
                            "pagination": {"limit": 50, "offset": 0, "total": 1},
                        }
                    elif action == "get":
                        response = {"data": record, "source_revision": 2}
                    expected.update(
                        method=method,
                        body=body,
                        response=response,
                        path=path + ("/record" if action in {"get", "update", "delete"} else ""),
                        params={"limit": "50", "offset": "0", **list_args}
                        if action == "list"
                        else {}
                        if action == "create"
                        else key,
                    )
                    result = await session.call_tool(
                        f"cronjob_{action}_{name.replace('-', '_')}", args
                    )
                    assert not result.is_error, (name, action, result)
                    assert tool_payload(result)["data"] == response["data"]

    asyncio.run(exercise())
    assert len(calls) == 70


@pytest.mark.parametrize("status", [302, 403, 404, 409, 422, 429, 503])
def test_crud_errors_are_sanitized_and_not_retried(settings, status):
    from app.cronjob import CronjobUpstream

    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="secret-provider-payload",
            headers={"location": "https://untrusted.example"},
        )

    service = DataService(settings)
    service.cronjob = CronjobUpstream(
        "http://cronjob.internal", "service", transport=httpx.MockTransport(handle)
    )

    async def exercise():
        async with sdk_session(service, identity("cronjob:write")) as session:
            result = await session.call_tool(
                "cronjob_delete_products",
                {
                    "key": {"shop_key": "shop-a", "sku": "tea"},
                    "idempotency_key": "same-key",
                },
            )
            assert result.is_error
            message = " ".join(c.text for c in result.content if c.type == "text")
            assert "secret-provider-payload" not in message
            assert "same idempotency_key" in message

    asyncio.run(exercise())
    assert len(calls) == 1


@pytest.mark.parametrize("admin", [False, True])
def test_sync_run_inspection_uses_correct_identity_and_route(settings, admin):
    from app.cronjob import CronjobUpstream

    if admin:
        settings.cronjob_admin_phones = {PHONE}
    service = DataService(settings)
    run = {
        "run_id": RUN_ID,
        "trigger": "mutation",
        "status": "succeeded",
        "created_at": TIME,
        "started_at": TIME,
        "finished_at": LATER,
        "attempts": 1,
        "minimum_revision": 1,
        "applied_revision": 2,
        "mutation_status": "applied",
        "error_stage": None,
        "error_code": None,
        "shop_counts": {"shop-a": {"orders": 1}, "unconfigured-shop": {"orders": 2}},
    }

    def handle(request):
        assert request.url.path == f"/v1/{'admin/' if admin else ''}sync-runs/{RUN_ID}"
        assert request.headers["X-Demo-User-Id"] == PHONE
        return httpx.Response(200, json=run)

    service.cronjob = CronjobUpstream(
        "http://cronjob.internal", "service", transport=httpx.MockTransport(handle)
    )

    async def exercise():
        async with sdk_session(service, identity("cronjob:read")) as session:
            result = await session.call_tool(
                "cronjob_get_sync_run", {"run_id": RUN_ID, "admin": admin}
            )
            assert not result.is_error
            assert tool_payload(result)["applied_revision"] == 2
            assert ("unconfigured-shop" in tool_payload(result)["shop_counts"]) == admin

    asyncio.run(exercise())


def test_stateful_crud_over_real_http(settings):
    """Exercise HTTP serialization and lifecycle without touching live business records."""
    from app.cronjob import CronjobUpstream

    records, receipts, calls = {}, {}, []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, payload):
            content = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            calls.append(self.command)
            assert self.headers["X-Demo-User-Id"] == PHONE
            url = urlsplit(self.path)
            params = parse_qs(url.query)
            assert params["shop_key"] == ["shop-a"]
            if url.path.endswith("/record"):
                record = records.get(params["sku"][0])
                self.respond(
                    200 if record else 404,
                    {"data": record, "source_revision": 2} if record else {"error": "NOT_FOUND"},
                )
            else:
                self.respond(
                    200,
                    {
                        "data": list(records.values()),
                        "source_revision": 2,
                        "pagination": {"limit": 50, "offset": 0, "total": len(records)},
                    },
                )

        def mutate(self):
            calls.append(self.command)
            assert self.headers["X-Demo-User-Id"] == PHONE
            key = self.headers["Idempotency-Key"]
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null"
            )
            if key not in receipts:
                if self.command == "POST":
                    assert body["sku"] not in records
                    records[body["sku"]] = body
                    data = body.copy()
                else:
                    sku = parse_qs(urlsplit(self.path).query)["sku"][0]
                    if self.command == "PATCH":
                        records[sku].update(body)
                        data = records[sku].copy()
                    else:
                        del records[sku]
                        data = {"deleted": True}
                receipts[key] = receipt(data)
            self.respond(202, receipts[key])

        do_POST = do_PATCH = do_DELETE = mutate

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    service = DataService(settings)
    service.cronjob = CronjobUpstream(f"http://127.0.0.1:{server.server_port}", "test-token")
    product = {
        **COMMON,
        "sku": "tea/+1",
        "name": "Tea",
        "unit_cost": "2.00",
        "cost_basis": "purchase",
    }
    key = {"shop_key": "shop-a", "sku": "tea/+1"}

    async def exercise():
        async with sdk_session(service, identity("cronjob:read", "cronjob:write")) as session:
            for _ in range(2):
                created = await session.call_tool(
                    "cronjob_create_products",
                    {
                        "data": product,
                        "idempotency_key": "create-1",
                    },
                )
                assert not created.is_error
                assert tool_payload(created)["sync_status"] == "queued"
            updated = await session.call_tool(
                "cronjob_update_products",
                {
                    "key": key,
                    "data": {"unit_cost": None},
                    "idempotency_key": "update-1",
                },
            )
            assert not updated.is_error
            fetched = await session.call_tool("cronjob_get_products", {"key": key})
            assert tool_payload(fetched)["data"]["unit_cost"] is None
            listed = await session.call_tool("cronjob_list_products", {})
            assert tool_payload(listed)["pagination"]["total"] == 1
            removed = await session.call_tool(
                "cronjob_delete_products",
                {
                    "key": key,
                    "idempotency_key": "delete-1",
                },
            )
            assert not removed.is_error
            missing = await session.call_tool("cronjob_get_products", {"key": key})
            assert missing.is_error

    try:
        asyncio.run(exercise())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert records == {}
    assert len(receipts) == 3
    assert calls == ["POST", "POST", "PATCH", "GET", "GET", "DELETE", "GET"]


def test_inventory_timestamp_key_accepts_equivalent_upstream_timezone(settings):
    from app.cronjob import CronjobUpstream

    record = {**COMMON, "sku": "tea", "location_id": "store", "observed_at": TIME, "available": 1}
    service = DataService(settings)
    service.cronjob = CronjobUpstream(
        "http://cronjob.internal",
        "service",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"data": record, "source_revision": 2},
            )
        ),
    )

    async def exercise():
        async with sdk_session(service, identity("cronjob:read")) as session:
            result = await session.call_tool(
                "cronjob_get_inventory",
                {
                    "key": {
                        **COMMON,
                        "sku": "tea",
                        "location_id": "store",
                        "observed_at": "2026-10-01T07:00:00+07:00",
                    }
                },
            )
            assert not result.is_error
            assert tool_payload(result)["data"]["observed_at"] == TIME

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "response",
    [
        {
            "data": {
                **COMMON,
                "sku": "wrong",
                "name": "Tea",
                "unit_cost": None,
                "cost_basis": "purchase",
            },
            "source_revision": 2,
        },
        {
            "data": {
                "shop_key": "other",
                "sku": "tea",
                "name": "Tea",
                "unit_cost": None,
                "cost_basis": "purchase",
            },
            "source_revision": 2,
        },
        {"data": {**COMMON, "sku": "tea"}, "source_revision": 2},
    ],
)
def test_wrong_record_shop_or_malformed_response_is_not_released(settings, response):
    from app.cronjob import CronjobUpstream

    service = DataService(settings)
    service.cronjob = CronjobUpstream(
        "http://cronjob.internal",
        "service",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
    )

    async def exercise():
        async with sdk_session(service, identity("cronjob:read")) as session:
            result = await session.call_tool(
                "cronjob_get_products", {"key": {**COMMON, "sku": "tea"}}
            )
            assert result.is_error
            assert result.structured_content is None

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "https://untrusted.example/v1/mock/products"),
        ("GET", "/v1/mock/products/../users"),
        ("GET", "/v1/mock/products?shop_key=other"),
        ("GET", "/v1/admin/mock/products"),
        ("GET", "/v1/mock/users"),
        ("POST", "/v1/mock/products/record"),
        ("DELETE", "/v1/mock/products"),
        ("PUT", "/v1/mock/products/record"),
    ],
)
def test_cronjob_transport_refuses_noncontract_routes(method, path):
    from app.cronjob import CronjobUpstream
    from app.upstream import IntegrationError

    upstream = CronjobUpstream("http://cronjob.internal", "service")
    with pytest.raises(IntegrationError, match="request is invalid"):
        asyncio.run(upstream.request(method, path))


def test_http_client_does_not_log_personal_record_keys(settings, caplog):
    from app.cronjob import CronjobUpstream

    settings.cronjob_admin_phones = {PHONE}
    service = DataService(settings)
    service.cronjob = CronjobUpstream(
        "http://cronjob.internal",
        "service",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "data": {"user_id": PHONE, "display_name": "Demo", "is_active": True},
                    "source_revision": 2,
                },
            )
        ),
    )

    async def exercise():
        async with sdk_session(service, identity("cronjob:read")) as session:
            result = await session.call_tool("cronjob_get_users", {"key": {"user_id": PHONE}})
            assert not result.is_error

    with caplog.at_level(logging.INFO):
        asyncio.run(exercise())
    assert PHONE[1:] not in caplog.text
