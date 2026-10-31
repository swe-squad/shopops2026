"""PR #6 schema compatibility and isolation against disposable PostgreSQL.

Set TEST_DATABASE_DSN and CRONJOB_SOURCE_DIR (the cronjob-server service directory).
The database must be empty; these tests create and remove their own schemas/roles.
Only SQL migrations cross the service boundary; no cronjob application imports.
"""

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app.auth import Principal
from app.database import Database
from app.query import compile_query
from app.settings import Catalog, Settings

SCHEMAS = ("access", "raw", "core", "mart", "sync", "mcp_control", "mcp_access", "mcp_data")
SHOPS = ("shopee:1001", "shopee:1002")


def seed(conn: psycopg.Connection) -> None:
    conn.execute("INSERT INTO access.merchants VALUES ('merchant', 'Test merchant', true)")
    for index, shop in enumerate(SHOPS, 1):
        document = f"document-{index}"
        conn.execute(
            "INSERT INTO raw.documents "
            "(document_id,merchant_id,platform,shop_id,resource,source_kind,captured_at,payload) "
            "VALUES (%s,'merchant','shopee',%s,'orders','demo_supplement',"
            "'2026-10-30T00:00:00Z','{\"private\":\"not-for-agents\"}')",
            (document, shop.split(":")[1]),
        )
        conn.execute(
            "INSERT INTO core.shops VALUES "
            "(%s,'merchant','shopee',%s,'Shop','VND','Asia/Ho_Chi_Minh','{}',%s)",
            (shop, shop.split(":")[1], document),
        )
        conn.execute(
            "INSERT INTO core.products VALUES (%s,'sku','Product',10,'known',%s)",
            (shop, document),
        )
        conn.execute(
            "INSERT INTO core.orders VALUES "
            "(%s,%s,'2026-10-29T00:00:00Z','2026-10-29T00:00:00Z','VND',"
            "'completed','COMPLETED',0,0,NULL,%s,%s)",
            (shop, f"order-{index}", document, document),
        )
        conn.execute(
            "INSERT INTO core.order_items VALUES (%s,%s,'line','sku',1,%s,'completed',%s)",
            (shop, f"order-{index}", 100 * index, document),
        )
        conn.execute(
            "INSERT INTO core.settlements VALUES (%s,%s,%s,0,0,%s,'2026-10-30T00:00:00Z',%s)",
            (shop, f"order-{index}", 3 * index, 97 * index, document),
        )


@pytest.fixture(scope="module")
def pipeline_database() -> Iterator[tuple[Database, str, dict[str, str]]]:
    dsn = os.environ.get("TEST_DATABASE_DSN")
    if not dsn:
        pytest.skip("Set TEST_DATABASE_DSN for real PostgreSQL integration checks")
    source_dir = os.environ.get("CRONJOB_SOURCE_DIR")
    if not source_dir:
        pytest.fail("Set CRONJOB_SOURCE_DIR to the PR #6 services/cronjob-server directory")
    migrations = sorted((Path(source_dir) / "app" / "migrations").glob("*.sql"))
    assert migrations, "No cronjob-server migrations found"

    from app.provision import provision

    suffix = uuid4().hex[:12]
    roles = {shop: f"mcp_pipeline_{suffix}_{index}" for index, shop in enumerate(SHOPS)}
    password = uuid4().hex
    catalog = Catalog.model_validate_json(Path("catalog.example.json").read_text())
    with psycopg.connect(dsn) as conn:
        existing = conn.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname=ANY(%s)", (list(SCHEMAS),)
        ).fetchall()
        assert not existing, "Refusing to run on a database containing application schemas"
        conn.execute("CREATE SCHEMA sync")
        for migration in migrations:
            conn.execute(migration.read_text(encoding="utf-8"))
        seed(conn)
        conn.execute(Path("migrations/001-control.sql").read_text())
        conn.execute(Path("migrations/002-pipeline-access.sql").read_text())
        for shop, role in roles.items():
            provision(conn, shop, role)
            conn.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
    settings = Settings(
        control_dsn=dsn,
        membership_dsn="postgresql://membership@localhost/test",
        public_url="https://mcp.test/mcp",
        datasets=catalog.datasets,
        shops={
            shop: {
                "query_dsn": make_conninfo(dsn, user=role, password=password),
                "datasets": [dataset.id for dataset in catalog.datasets],
            }
            for shop, role in roles.items()
        },
    )
    try:
        yield Database(settings), dsn, roles
    finally:
        with psycopg.connect(dsn) as conn:
            for schema in reversed(SCHEMAS):
                conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
            for role in roles.values():
                conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
                conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_real_pipeline_catalog_and_two_shop_isolation(pipeline_database) -> None:
    database, _, _ = pipeline_database

    async def check() -> None:
        for index, shop in enumerate(SHOPS, 1):
            who = Principal(subject="agent", shop=shop, scopes={"data:read"})
            grant = {
                "datasets": {d.id: d.columns for d in database.settings.datasets},
                "start": "2000-01-01T00:00:00Z",
                "end": "2100-01-01T00:00:00Z",
            }
            for dataset in database.settings.datasets:
                await database.query(
                    who, compile_query(f"SELECT * FROM {dataset.id} LIMIT 0", [dataset], grant)
                )
            result = await database.query(
                who,
                compile_query(
                    "SELECT order_id, gross_sales FROM order_economics",
                    database.settings.datasets,
                ),
            )
            assert result["rows"] == [
                {"order_id": f"order-{index}", "gross_sales": f"{100 * index}.00"}
            ]
            raw = await database.query(
                who,
                compile_query(
                    "SELECT order_id, fee FROM settlement_details",
                    database.settings.datasets,
                    grant,
                ),
            )
            assert raw["rows"] == [{"order_id": f"order-{index}", "fee": f"{3 * index}.00"}]

    asyncio.run(check())


def test_query_login_cannot_bypass_projections_or_impersonate(pipeline_database) -> None:
    database, _, roles = pipeline_database
    dsn = database.settings.shops[SHOPS[0]].query_dsn.get_secret_value()
    with psycopg.connect(dsn, autocommit=True) as conn:
        for relation in (
            "raw.documents",
            "core.orders",
            "mart.order_economics",
            "access.users",
            "mcp_control.results",
            "mcp_access.shop_roles",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql.SQL("SELECT * FROM {} LIMIT 1").format(sql.SQL(relation)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(roles[SHOPS[1]])))
        # Caller-controlled session settings must never select database tenancy.
        conn.execute("SELECT set_config('app.shop_key', %s, false)", (SHOPS[1],))
        assert conn.execute("SELECT order_id FROM mcp_data.order_economics").fetchall() == [
            ("order-1",)
        ]
        for privilege in ("INSERT", "UPDATE", "DELETE"):
            assert conn.execute(
                "SELECT has_table_privilege(current_user, 'mcp_data.order_economics', %s)",
                (privilege,),
            ).fetchone() == (False,)


def test_provisioning_is_repeatable_but_never_reassigns_identity(pipeline_database) -> None:
    from app.provision import provision

    _, dsn, roles = pipeline_database
    with psycopg.connect(dsn) as conn:
        provision(conn, SHOPS[0], roles[SHOPS[0]])
    with psycopg.connect(dsn) as conn, pytest.raises(ValueError):
        provision(conn, SHOPS[1], roles[SHOPS[0]])


def test_pipeline_can_publish_after_query_roles_are_provisioned(pipeline_database) -> None:
    database, dsn, _ = pipeline_database
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO core.products VALUES (%s,'sku','Updated product',15,'known','document-1') "
            "ON CONFLICT (shop_key,sku) DO UPDATE SET unit_cost=EXCLUDED.unit_cost",
            (SHOPS[0],),
        )
    who = Principal(subject="agent", shop=SHOPS[0], scopes={"data:read"})
    result = asyncio.run(
        database.query(
            who,
            compile_query(
                "SELECT contribution_margin FROM order_economics", database.settings.datasets
            ),
        )
    )
    assert result["rows"] == [{"contribution_margin": "82.00"}]


def test_deleted_shop_cannot_rebind_query_login_to_new_merchant(pipeline_database) -> None:
    from app.provision import provision

    _, dsn, roles = pipeline_database
    shop = "shopee:1003"
    role = f"mcp_pipeline_{uuid4().hex[:12]}_rebound"
    password = uuid4().hex
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO core.shops VALUES "
            "(%s,'merchant','shopee','1003','Old shop','VND','Asia/Ho_Chi_Minh','{}','document-1')",
            (shop,),
        )
        provision(conn, shop, role)
        conn.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password))
        )
    roles[shop] = role
    query_dsn = make_conninfo(dsn, user=role, password=password)
    with psycopg.connect(query_dsn) as conn:
        assert conn.execute("SELECT mcp_access.current_shop()").fetchone() == (shop,)

    # A stale login mapping must not prevent the pipeline applying a shop tombstone.
    with psycopg.connect(dsn) as conn:
        assert conn.execute("DELETE FROM core.shops WHERE shop_key=%s", (shop,)).rowcount == 1
    with psycopg.connect(query_dsn) as conn:
        assert conn.execute("SELECT mcp_access.current_shop()").fetchone() == (None,)

    with psycopg.connect(dsn) as conn:
        conn.execute("INSERT INTO access.merchants VALUES ('new-merchant','New merchant',true)")
        conn.execute(
            "INSERT INTO raw.documents "
            "(document_id,merchant_id,platform,shop_id,resource,source_kind,captured_at,payload) "
            "VALUES ('new-document','new-merchant','shopee','1003','orders','demo_supplement',"
            "'2026-10-30T00:00:00Z','{}')"
        )
        conn.execute(
            "INSERT INTO core.shops VALUES "
            "(%s,'new-merchant','shopee','1003','New shop','VND','Asia/Ho_Chi_Minh','{}',"
            "'new-document')",
            (shop,),
        )
        conn.execute(
            "INSERT INTO core.products VALUES (%s,'sku','Product',10,'known','new-document')",
            (shop,),
        )
        conn.execute(
            "INSERT INTO core.orders VALUES "
            "(%s,'new-order','2026-10-29T00:00:00Z','2026-10-29T00:00:00Z','VND',"
            "'completed','COMPLETED',0,0,NULL,'new-document','new-document')",
            (shop,),
        )
        conn.execute(
            "INSERT INTO core.order_items VALUES "
            "(%s,'new-order','line','sku',1,100,'completed','new-document')",
            (shop,),
        )
        assert conn.execute(
            "SELECT order_id FROM mart.order_economics WHERE shop_key=%s", (shop,)
        ).fetchall() == [("new-order",)]
    with psycopg.connect(query_dsn) as conn:
        assert conn.execute("SELECT mcp_access.current_shop()").fetchone() == (None,)
        assert conn.execute("SELECT order_id FROM mcp_data.order_economics").fetchall() == []
    with psycopg.connect(dsn) as conn, pytest.raises(ValueError):
        provision(conn, shop, role)
