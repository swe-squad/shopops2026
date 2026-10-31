"""Real phone-to-MCP-to-PostgreSQL checks using a disposable TEST_DATABASE_DSN."""

import asyncio
import json
import sys
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo
from starlette.testclient import TestClient

from app.main import create_app
from app.settings import Dataset
from tests import test_database

database = test_database.database

ALICE = "+84900000001"
AGENCY = "+84900000003"
SHOP_A = "lazada:1001"
SHOP_B = "shopify:1001"


@pytest.fixture
def phone_database(database, monkeypatch):
    dsn = database.settings.control_dsn.get_secret_value()
    fixtures = Path("../../data_preparation/data_mock_raw_for_mock_server")
    with psycopg.connect(dsn, autocommit=True) as conn:
        existing = conn.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname=ANY(%s)",
            (["access", "raw", "core"],),
        ).fetchall()
        assert not existing, "Use an empty disposable database"
        conn.execute((fixtures / "schema.sql").read_text(encoding="utf-8"))
        conn.execute((fixtures / "seed.sql").read_text(encoding="utf-8"))
        conn.execute(Path("migrations/003-phone-membership.sql").read_text())
    settings = database.settings.model_copy(
        update={
            "membership_dsn": type(database.settings.control_dsn)(
                make_conninfo(dsn, user="mcp_membership")
            ),
            "shops": {SHOP_A: database.settings.shops["a"], SHOP_B: database.settings.shops["b"]},
            "datasets": [
                Dataset(
                    id="orders",
                    relation="mart.orders",
                    layer="mart",
                    description="Test totals",
                    columns=["amount"],
                )
            ],
        }
    )
    for shop in settings.shops.values():
        shop.datasets = ["orders"]
    monkeypatch.setattr("app.settings.Settings.load", lambda: settings)
    options = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
    try:
        with TestClient(
            create_app(), base_url="https://mcp.test", backend_options=options
        ) as client:
            yield client, dsn, settings.membership_dsn.get_secret_value()
    finally:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("DROP SCHEMA core CASCADE")
            conn.execute("DROP SCHEMA raw CASCADE")
            conn.execute("DROP SCHEMA access CASCADE")
            conn.execute("DROP ROLE mcp_membership")


def rpc(client, phone, method, params):
    return client.post(
        "/mcp",
        headers={"X-Phone-Number": phone, "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )


def call(client, phone, name, arguments):
    response = rpc(client, phone, "tools/call", {"name": name, "arguments": arguments})
    assert response.status_code == 200, response.text
    if response.headers["content-type"].startswith("text/event-stream"):
        body = json.loads(
            next(line[6:] for line in response.text.splitlines() if line.startswith("data: "))
        )
    else:
        body = response.json()
    return body["result"]


def payload(result):
    assert not result.get("isError"), result
    return result["structuredContent"]


def test_real_http_multi_shop_queries_and_saved_result_ownership(phone_database):
    client, _, _ = phone_database
    assert (
        rpc(
            client,
            AGENCY,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "phone-test", "version": "1"},
            },
        ).status_code
        == 200
    )
    assert payload(call(client, AGENCY, "list_shops", {}))["shops"] == [
        {"shop_key": SHOP_A},
        {"shop_key": SHOP_B},
    ]
    assert payload(call(client, ALICE, "list_shops", {}))["shops"] == [{"shop_key": SHOP_A}]
    results = []
    for shop, expected in [(SHOP_A, "10"), (SHOP_B, "999")]:
        result = payload(
            call(
                client,
                AGENCY,
                "query_mart",
                {
                    "shop_key": shop,
                    "query": "SELECT sum(amount) AS total FROM orders",
                },
            )
        )
        assert result["preview"] == [{"total": expected}]
        assert result["shop_key"] == shop
        results.append(result["result_id"])
    args = {"shop_key": SHOP_A, "result_id": results[0]}
    assert payload(call(client, AGENCY, "read_result", args))["rows"] == [{"total": "10"}]
    assert call(client, AGENCY, "read_result", args | {"shop_key": SHOP_B})["isError"]
    assert call(client, ALICE, "read_result", args)["isError"]
    assert call(
        client,
        ALICE,
        "query_mart",
        {
            "shop_key": SHOP_B,
            "query": "SELECT * FROM orders",
        },
    )["isError"]
    assert call(client, ALICE, "drop_temp_mart", args)["isError"] is False
    # A deletion using a different subject is a no-op, never deletes the owner's result.
    assert payload(call(client, AGENCY, "read_result", args))["rows"]


@pytest.mark.parametrize("phone", ["+84900000004", "+84900000005", "+84900000006", "+84999999999"])
def test_real_inactive_unassigned_and_unknown_users_cannot_call_tools(phone_database, phone):
    client, _, _ = phone_database
    response = rpc(client, phone, "tools/list", {})
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}


@pytest.mark.parametrize("relation", ["users", "merchants", "merchant_memberships"])
def test_real_membership_changes_block_saved_result_access(phone_database, relation):
    client, dsn, _ = phone_database
    result = payload(call(client, ALICE, "query_mart", {"query": "SELECT * FROM orders"}))
    with psycopg.connect(dsn) as conn:
        # Identifiers are from this fixed parametrization, never request input.
        conn.execute(
            psycopg.sql.SQL("UPDATE access.{} SET is_active=false").format(
                psycopg.sql.Identifier(relation)
            )
        )
    assert (
        rpc(
            client,
            ALICE,
            "tools/call",
            {
                "name": "read_result",
                "arguments": {"result_id": result["result_id"]},
            },
        ).status_code
        == 401
    )


def test_revoking_one_shop_preserves_other_shops_but_denies_old_results(phone_database):
    client, dsn, _ = phone_database
    result = payload(
        call(client, AGENCY, "query_mart", {"shop_key": SHOP_A, "query": "SELECT * FROM orders"})
    )
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "UPDATE access.merchant_memberships SET is_active=false "
            "WHERE user_id=%s AND merchant_id=%s",
            (AGENCY, "merchant-demo-001"),
        )
    assert payload(call(client, AGENCY, "list_shops", {}))["shops"] == [{"shop_key": SHOP_B}]
    assert call(
        client,
        AGENCY,
        "read_result",
        {
            "shop_key": SHOP_A,
            "result_id": result["result_id"],
        },
    )["isError"]
    remaining = payload(call(client, AGENCY, "query_mart", {"query": "SELECT * FROM orders"}))
    assert remaining["shop_key"] == SHOP_B
    assert remaining["preview"] == [{"amount": "999"}]


def test_membership_login_cannot_read_source_records_or_write(phone_database):
    _, _, dsn = phone_database
    with psycopg.connect(dsn, autocommit=True) as conn:
        assert conn.execute("SHOW default_transaction_read_only").fetchone()[0] == "on"
        for query in [
            "SELECT * FROM access.users",
            "SELECT * FROM core.orders",
            "SELECT role FROM access.user_shop_access",
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(query)
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("DELETE FROM access.users")
