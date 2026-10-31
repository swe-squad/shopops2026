"""Real SDK protocol checks with fake database/network boundaries."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import anyio
import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
from mcp.types import CallToolResult

from app.auth import Identity, principal
from app.server import build_server
from app.service import DataService
from app.settings import Dataset, Settings, Shop


@pytest.fixture
def settings() -> Settings:
    return Settings(
        control_dsn="postgresql://control@localhost/test",
        membership_dsn="postgresql://membership@localhost/test",
        public_url="https://mcp.example/mcp",
        datasets=[
            Dataset(
                id="orders",
                relation="analytics.orders",
                layer="mart",
                description="Daily order totals",
                columns=["status", "total"],
            ),
            Dataset(
                id="hidden",
                relation="analytics.hidden",
                layer="mart",
                description="Another shop",
                columns=["total"],
            ),
        ],
        shops={"shop-a": Shop(query_dsn="postgresql://shop_a@localhost/test", datasets=["orders"])},
    )


@asynccontextmanager
async def sdk_session(
    service: DataService, identity: Identity | None = None
) -> AsyncIterator[ClientSession]:
    identity = identity or Identity(subject="+84900000001", shops={"shop-a"}, scopes={"data:read"})
    context = principal.set(identity)
    try:
        server = build_server(service)._lowlevel_server
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            async with anyio.create_task_group() as group:
                group.start_soon(
                    server.run, *server_streams, server.create_initialization_options()
                )
                async with ClientSession(*client_streams, read_timeout_seconds=5) as session:
                    await session.initialize()
                    yield session
                group.cancel_scope.cancel()
    finally:
        principal.reset(context)


def tool_payload(result: CallToolResult) -> dict:
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(item.text for item in result.content if item.type == "text"))


def test_sdk_lists_and_calls_catalog_query_and_result_tools(settings: Settings) -> None:
    service = DataService(settings)
    service.db = AsyncMock()
    service.db.query.return_value = {
        "columns": ["status", "total"],
        "rows": [{"status": "ready", "total": 2}],
        "truncated": False,
    }
    service.db.save.return_value = "result-a"
    service.db.read.return_value = {
        "grants": [],
        "expires_at": datetime.now(UTC) + timedelta(minutes=10),
        "payload": {
            "columns": ["status"],
            "rows": [{"status": "first"}, {"status": "second"}],
            "truncated": False,
        },
    }

    async def exercise() -> None:
        async with sdk_session(service) as session:
            listed = await session.list_tools()
            assert {"search_catalog", "query_mart", "read_result"}.issubset(
                {tool.name for tool in listed.tools}
            )
            catalog = await session.call_tool("search_catalog", {"query": "daily"})
            assert not catalog.is_error
            assert [item["id"] for item in tool_payload(catalog)["datasets"]] == ["orders"]
            queried = await session.call_tool("query_mart", {"query": "SELECT * FROM orders"})
            assert not queried.is_error
            assert tool_payload(queried)["result_id"] == "result-a"
            assert tool_payload(queried)["preview"] == [{"status": "ready", "total": 2}]
            page = await session.call_tool("read_result", {"result_id": "result-a", "limit": 1})
            assert not page.is_error
            assert tool_payload(page)["rows"] == [{"status": "first"}]
            assert tool_payload(page)["next_offset"] == 1

    asyncio.run(exercise())
    assert service.db.query.await_args.args[0].shop == "shop-a"
    assert '"analytics"."orders"' in service.db.query.await_args.args[1]


def test_sdk_rejects_invalid_pages_and_unsafe_sql_before_database(settings: Settings) -> None:
    service = DataService(settings)
    service.db = AsyncMock()

    async def exercise() -> None:
        async with sdk_session(service) as session:
            for arguments in [
                {"result_id": "result-a", "offset": -1},
                {"result_id": "result-a", "limit": 0},
                {"result_id": "result-a", "limit": 101},
            ]:
                rejected = await session.call_tool("read_result", arguments)
                assert rejected.is_error
            for query in [
                "DELETE FROM orders",
                "SELECT * FROM hidden",
                "SELECT pg_sleep(1) FROM orders",
            ]:
                rejected = await session.call_tool("query_mart", {"query": query})
                assert rejected.is_error
                text = " ".join(item.text for item in rejected.content if item.type == "text")
                assert "Operation denied" in text
                assert "postgresql://" not in text

    asyncio.run(exercise())
    service.db.query.assert_not_awaited()
    service.db.read.assert_not_awaited()


def test_one_phone_can_discover_and_query_each_authorized_shop(settings):
    settings.shops["shop-b"] = Shop(query_dsn="postgresql://b@localhost/test", datasets=["hidden"])
    service = DataService(settings)
    service.db = AsyncMock()
    service.db.query.return_value = {"columns": ["total"], "rows": [], "truncated": False}
    service.db.save.return_value = "result-b"
    identity = Identity(subject="+84900000001", shops={"shop-a", "shop-b"}, scopes={"data:read"})

    async def exercise():
        async with sdk_session(service, identity) as session:
            shops = await session.call_tool("list_shops", {})
            assert not shops.is_error
            assert tool_payload(shops)["shops"] == [{"shop_key": "shop-a"}, {"shop_key": "shop-b"}]
            for shop, dataset in [("shop-a", "orders"), ("shop-b", "hidden")]:
                catalog = await session.call_tool("search_catalog", {"shop_key": shop})
                assert not catalog.is_error
                assert [d["id"] for d in tool_payload(catalog)["datasets"]] == [dataset]
                result = await session.call_tool(
                    "query_mart", {"query": f"SELECT * FROM {dataset}", "shop_key": shop}
                )
                assert not result.is_error
                assert service.db.query.await_args.args[0].shop == shop
                assert service.db.query.await_args.args[0].subject == identity.subject
                assert tool_payload(result)["shop_key"] == shop

    asyncio.run(exercise())


@pytest.mark.parametrize("shop_key", [None, "not-authorized", ""])
def test_multi_shop_tools_reject_missing_or_unauthorized_selection(settings, shop_key):
    service = DataService(settings)
    service.db = AsyncMock()
    service.ingestion = AsyncMock()
    service.approval = AsyncMock()
    identity = Identity(subject="+84900000001", shops={"shop-a", "shop-b"}, scopes={"data:read"})
    calls = {
        "search_catalog": {},
        "describe_dataset": {"dataset_id": "orders"},
        "query_mart": {"query": "SELECT * FROM orders"},
        "query_raw": {"query": "SELECT * FROM orders", "grant_id": "grant"},
        "create_temp_mart": {"query": "SELECT * FROM orders"},
        "query_temp_mart": {"query": "SELECT * FROM temp", "result_id": "result"},
        "read_result": {"result_id": "result"},
        "drop_temp_mart": {"result_id": "result"},
        "request_raw_access": {"datasets": {}, "start": "a", "end": "b", "reason": "test"},
        "request_refresh": {
            "resource": "orders",
            "start": "a",
            "end": "b",
            "idempotency_key": "key",
        },
        "get_operation": {"operation_id": "operation"},
    }

    async def exercise():
        async with sdk_session(service, identity) as session:
            for tool, args in calls.items():
                result = await session.call_tool(tool, args | {"shop_key": shop_key})
                assert result.is_error, tool
                assert "Choose an authorized shop_key" in " ".join(
                    item.text for item in result.content if item.type == "text"
                )

    asyncio.run(exercise())
    assert not service.db.mock_calls
    assert not service.ingestion.mock_calls
    assert not service.approval.mock_calls
