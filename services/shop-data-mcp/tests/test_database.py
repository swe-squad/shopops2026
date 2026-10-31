"""Real PostgreSQL checks. Set TEST_DATABASE_DSN to a disposable database only."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from app.auth import Principal
from app.database import Database
from app.query import compile_query
from app.settings import Dataset, Settings


@pytest.fixture
def database():
    dsn = os.environ.get("TEST_DATABASE_DSN")
    if not dsn:
        pytest.skip("Set TEST_DATABASE_DSN for real PostgreSQL integration checks")
    # Caller must supply a fresh disposable DB; tests deliberately refuse existing objects.
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE ROLE mcp_test_a LOGIN NOSUPERUSER NOBYPASSRLS")
        conn.execute("CREATE ROLE mcp_test_b LOGIN NOSUPERUSER NOBYPASSRLS")
        conn.execute("CREATE SCHEMA mart")
        conn.execute("CREATE TABLE mart.orders(shop text, amount numeric, private text)")
        conn.execute(
            "INSERT INTO mart.orders VALUES ('mcp_test_a',10,'hidden'),('mcp_test_b',999,'secret')"
        )
        conn.execute("ALTER TABLE mart.orders ENABLE ROW LEVEL SECURITY")
        conn.execute("ALTER TABLE mart.orders FORCE ROW LEVEL SECURITY")
        conn.execute("CREATE POLICY tenant ON mart.orders USING(shop=current_user)")
        conn.execute("GRANT USAGE ON SCHEMA mart TO mcp_test_a,mcp_test_b")
        conn.execute("GRANT SELECT ON mart.orders TO mcp_test_a,mcp_test_b")
        conn.execute(Path("migrations/001-control.sql").read_text())
    settings = Settings(
        control_dsn=dsn,
        membership_dsn="postgresql://membership@localhost/test",
        public_url="https://mcp.test/mcp",
        datasets=[],
        shops={
            "a": {"query_dsn": make_conninfo(dsn, user="mcp_test_a"), "datasets": []},
            "b": {"query_dsn": make_conninfo(dsn, user="mcp_test_b"), "datasets": []},
        },
    )
    yield Database(settings)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP SCHEMA mart CASCADE")
        conn.execute("DROP SCHEMA mcp_control CASCADE")
        conn.execute("DROP ROLE mcp_test_a, mcp_test_b")


def test_real_isolation_results_and_refresh(database):
    async def check():
        a = Principal(subject="agent", shop="a", scopes={"data:read"})
        b = Principal(subject="agent", shop="b", scopes={"data:read"})
        dataset = Dataset(
            id="orders",
            relation="mart.orders",
            layer="mart",
            description="test",
            columns=["amount"],
        )
        query = compile_query("SELECT sum(amount) AS total FROM orders", [dataset])
        assert (await database.query(a, query))["rows"] == [{"total": "10"}]
        assert (await database.query(b, query))["rows"] == [{"total": "999"}]
        # Repeated identity changes use fresh connections; no pooled scope leakage.
        assert (await database.query(a, query))["rows"] == [{"total": "10"}]
        with pytest.raises(psycopg.errors.UndefinedColumn):
            await database.query(a, compile_query("SELECT private FROM orders", [dataset]))
        payload = {"columns": ["total"], "rows": [{"total": "10"}], "truncated": False}
        key = await database.save(a, payload, [], datetime.now(UTC) + timedelta(seconds=60))
        assert (await database.read(a, key))["payload"] == payload
        with pytest.raises(ValueError):
            await database.read(b, key)
        temp_query = compile_query(
            "SELECT cast(total AS INT) + 1 AS result FROM temp", [], temporary={"temp": payload}
        )
        assert (await database.query(a, temp_query))["rows"] == [{"result": 11}]
        body = {"resource": "orders"}
        assert (await database.reserve_refresh(a, "key", body))["operation_id"] is None
        await database.attach_operation(a, "key", "job1")
        assert (await database.reserve_refresh(a, "key", body))["operation_id"] == "job1"
        assert not await database.operation_owned(b, "job1")
        with pytest.raises(ValueError):
            await database.reserve_refresh(a, "key", {"resource": "other"})
        with pytest.raises(ValueError):
            await database.reserve_refresh(a, "key2", body)
        await database.drop(a, key)
        with pytest.raises(ValueError):
            await database.read(a, key)

    asyncio.run(check())
