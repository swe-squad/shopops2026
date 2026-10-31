"""Real SDK protocol and signed JWT checks with fake database/network boundaries."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import anyio
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams
from mcp.types import CallToolResult
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.auth import Authentication, Principal, principal
from app.database import Database
from app.server import build_server
from app.service import DataService
from app.settings import Dataset, Settings, Shop


@pytest.fixture
def settings() -> Settings:
    return Settings(
        control_dsn="postgresql://control@localhost/test",
        issuer="https://issuer.example",
        audience="https://mcp.example",
        jwks_url="https://issuer.example/jwks",
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
async def sdk_session(service: DataService) -> AsyncIterator[ClientSession]:
    identity = Principal(subject="agent-a", shop="shop-a", scopes={"data:read"})
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


@pytest.fixture(scope="module")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def auth_context(
    settings: Settings, signing_key: rsa.RSAPrivateKey, monkeypatch: pytest.MonkeyPatch
) -> SimpleNamespace:
    async def protected(request: Request) -> JSONResponse:
        who = principal.get()
        return JSONResponse({"subject": who.subject, "shop": who.shop})

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    cursor = AsyncMock()
    cursor.fetchone.return_value = None
    connection = AsyncMock()
    connection.__aenter__.return_value = connection
    connection.execute.return_value = cursor
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr(Database, "connect", connect)
    app = Authentication(
        Starlette(routes=[Route("/protected", protected), Route("/health", health)]), settings
    )
    app.keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=signing_key.public_key())
    )
    return SimpleNamespace(
        client=TestClient(app), cursor=cursor, connection=connection, connect=connect
    )


def signed_token(settings: Settings, signing_key: rsa.RSAPrivateKey, **changes: Any) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": settings.issuer,
        "aud": settings.audience,
        "sub": "agent-a",
        "shop_key": "shop-a",
        "scope": "data:read",
        "iat": now - timedelta(seconds=5),
        "exp": now + timedelta(minutes=10),
        "jti": "token-a",
    }
    claims.update(changes)
    return jwt.encode(claims, signing_key, algorithm="RS256")


def test_signed_token_sets_verified_context_and_checks_revocation(
    auth_context: SimpleNamespace,
    settings: Settings,
    signing_key: rsa.RSAPrivateKey,
) -> None:
    token = signed_token(settings, signing_key)
    response = auth_context.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"subject": "agent-a", "shop": "shop-a"}
    assert auth_context.connection.execute.await_args.args[1] == ("token-a",)
    with pytest.raises(LookupError):
        principal.get()


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://untrusted.example"},
        {"aud": "https://other.example"},
        {"exp": datetime(2000, 1, 1, tzinfo=UTC)},
        {"shop_key": "shop-b"},
        {"scope": "raw:read"},
        {"exp": datetime.now(UTC) + timedelta(hours=2)},
    ],
)
def test_invalid_signed_claims_are_unauthorized(
    auth_context: SimpleNamespace,
    settings: Settings,
    signing_key: rsa.RSAPrivateKey,
    changes: dict,
) -> None:
    token = signed_token(settings, signing_key, **changes)
    response = auth_context.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}
    auth_context.connect.assert_not_awaited()


def test_revoked_jti_is_unauthorized(
    auth_context: SimpleNamespace, settings: Settings, signing_key: rsa.RSAPrivateKey
) -> None:
    auth_context.cursor.fetchone.return_value = {"revoked": True}
    token = signed_token(settings, signing_key)
    response = auth_context.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert auth_context.connection.execute.await_args.args[1] == ("token-a",)


def test_revocation_database_outage_fails_closed(
    auth_context: SimpleNamespace,
    settings: Settings,
    signing_key: rsa.RSAPrivateKey,
) -> None:
    auth_context.connect.side_effect = RuntimeError("private database secret")
    token = signed_token(settings, signing_key)
    response = auth_context.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "secret" not in response.text


def test_health_is_public_and_protected_route_requires_token(auth_context: SimpleNamespace) -> None:
    assert auth_context.client.get("/health").status_code == 200
    assert auth_context.client.get("/protected").status_code == 401
    auth_context.connect.assert_not_awaited()


def test_invalid_authorization_bytes_are_unauthorized(auth_context: SimpleNamespace) -> None:
    response = auth_context.client.get("/protected", headers=[(b"authorization", b"Bearer \xff")])
    assert response.status_code == 401


@pytest.mark.parametrize("kind", ["signature", "algorithm", "missing-jti"])
def test_untrusted_signature_algorithm_and_missing_jti_are_unauthorized(
    auth_context: SimpleNamespace,
    settings: Settings,
    signing_key: rsa.RSAPrivateKey,
    kind: str,
) -> None:
    token = signed_token(settings, signing_key)
    if kind == "signature":
        header, body, signature = token.split(".")
        signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        token = ".".join([header, body, signature])
    else:
        claims = jwt.decode(token, options={"verify_signature": False})
        if kind == "algorithm":
            token = jwt.encode(claims, "unit-test-key-at-least-32-bytes-long", algorithm="HS256")
        else:
            claims.pop("jti")
            token = jwt.encode(claims, signing_key, algorithm="RS256")
    response = auth_context.client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    auth_context.connect.assert_not_awaited()
