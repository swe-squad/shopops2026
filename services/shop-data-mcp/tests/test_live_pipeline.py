"""SDK-to-HTTP-to-PostgreSQL integration against disposable running services.

The harness owns process/database cleanup. MCP uses the official in-memory SDK
transport with an already verified identity; cronjob calls use real HTTP bearer
authentication and queries use real restricted PostgreSQL logins.
"""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import anyio
import psycopg
import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
from mcp.types import CallToolResult
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.auth import Principal, principal
from app.provision import provision
from app.server import build_server
from app.service import DataService
from app.settings import Catalog, Settings

SHOPS = ("lazada:1001", "shopify:1001")


@pytest.fixture
def live_service() -> tuple[DataService, int]:
    names = (
        "MCP_PIPELINE_TEST_DSN",
        "MCP_CONTROL_TEST_DSN",
        "MCP_CRONJOB_TEST_URL",
        "MCP_CRONJOB_TEST_TOKEN",
    )
    values = {name: os.environ.get(name) for name in names}
    if not any(values.values()):
        pytest.skip("Run the live pipeline integration harness to supply disposable services")
    assert all(values.values()), "The live pipeline harness must set all MCP integration variables"
    derived_dsn = values["MCP_PIPELINE_TEST_DSN"]
    control_dsn = values["MCP_CONTROL_TEST_DSN"]
    catalog = Catalog.model_validate_json(Path("catalog.example.json").read_text())
    password = uuid4().hex
    roles = {shop: f"mcp_live_{uuid4().hex[:12]}" for shop in SHOPS}
    with psycopg.connect(derived_dsn) as conn:
        conn.execute(Path("migrations/002-pipeline-access.sql").read_text())
        for shop, role in roles.items():
            provision(conn, shop, role)
            conn.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
        expected = conn.execute(
            "SELECT count(*) FROM mart.order_economics WHERE shop_key=%s", (SHOPS[0],)
        ).fetchone()[0]
        assert expected > 0, "The pipeline must have published the initial fixture snapshot"
    with psycopg.connect(control_dsn) as conn:
        conn.execute(Path("migrations/001-control.sql").read_text())
    settings = Settings(
        control_dsn=control_dsn,
        issuer="https://issuer.test",
        audience="https://mcp.test/mcp",
        jwks_url="https://issuer.test/jwks",
        public_url="https://mcp.test/mcp",
        datasets=catalog.datasets,
        shops={
            shop: {
                "query_dsn": make_conninfo(derived_dsn, user=role, password=password),
                "datasets": [dataset.id for dataset in catalog.datasets],
            }
            for shop, role in roles.items()
        },
        ingestion_url=values["MCP_CRONJOB_TEST_URL"],
        ingestion_token=values["MCP_CRONJOB_TEST_TOKEN"],
    )
    return DataService(settings), expected


@asynccontextmanager
async def sdk_session(service: DataService, shop: str) -> AsyncIterator[ClientSession]:
    identity = Principal(subject="agent-a", shop=shop, scopes={"data:read", "data:refresh"})
    context = principal.set(identity)
    try:
        server = build_server(service)._lowlevel_server
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            async with anyio.create_task_group() as group:
                group.start_soon(
                    server.run, *server_streams, server.create_initialization_options()
                )
                async with ClientSession(*client_streams, read_timeout_seconds=20) as session:
                    await session.initialize()
                    yield session
                group.cancel_scope.cancel()
    finally:
        principal.reset(context)


def payload(result: CallToolResult) -> dict:
    assert not result.is_error, "The live MCP tool returned an error"
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(next(item.text for item in result.content if item.type == "text"))


def test_live_agent_query_refresh_poll_and_cross_shop_denial(live_service) -> None:
    service, expected = live_service

    async def exercise() -> None:
        async with sdk_session(service, SHOPS[0]) as session:
            tools = await session.list_tools()
            assert {"query_mart", "request_refresh", "get_operation"}.issubset(
                tool.name for tool in tools.tools
            )
            catalog = payload(await session.call_tool("search_catalog", {}))
            assert {item["id"] for item in catalog["datasets"]} == {
                dataset.id for dataset in service.settings.datasets
            }
            query = {"query": "SELECT count(*) AS total FROM order_economics"}
            before = payload(await session.call_tool("query_mart", query))
            assert before["preview"] == [{"total": expected}]
            assert not before["truncated"]

            now = datetime.now(UTC)
            refresh = {
                "resource": "snapshot",
                "start": (now - timedelta(days=2)).isoformat(),
                "end": (now - timedelta(days=1)).isoformat(),
                "idempotency_key": uuid4().hex,
            }
            accepted = payload(await session.call_tool("request_refresh", refresh))
            operation_id = accepted["operation_id"]
            async with asyncio.timeout(30):
                while True:
                    operation = payload(
                        await session.call_tool("get_operation", {"operation_id": operation_id})
                    )
                    assert operation["status"] not in {"failed", "cancelled", "partial"}
                    if operation["status"] == "snapshot_ready":
                        break
                    await asyncio.sleep(0.2)
            assert operation["coverage"] is None
            assert operation["refresh_mode"] == "full_snapshot"
            assert operation["applied_source_revision"] >= 1
            replay = payload(await session.call_tool("request_refresh", refresh))
            assert replay["operation_id"] == operation_id
            after = payload(await session.call_tool("query_mart", query))
            assert after["preview"] == [{"total": expected}]
            saved = payload(
                await session.call_tool("read_result", {"result_id": after["result_id"]})
            )
            assert saved["rows"] == after["preview"]

        async with sdk_session(service, SHOPS[1]) as other_shop:
            operation_denied = await other_shop.call_tool(
                "get_operation", {"operation_id": operation_id}
            )
            assert operation_denied.is_error
            result_denied = await other_shop.call_tool(
                "read_result", {"result_id": after["result_id"]}
            )
            assert result_denied.is_error

    asyncio.run(exercise())
