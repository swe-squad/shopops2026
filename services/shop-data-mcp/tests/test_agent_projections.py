"""T10 projections against disposable PostgreSQL, including real query logins."""

from pathlib import Path

import psycopg
import pytest

from tests.test_pipeline_database import SHOPS, pipeline_database  # noqa: F401


@pytest.fixture(scope="module", autouse=True)
def agent_projection_grain_privacy_and_isolation(pipeline_database):  # noqa: F811
    database, dsn, _ = pipeline_database
    with psycopg.connect(dsn) as conn:
        conn.execute(Path("migrations/004-agent-projections.sql").read_text())
        conn.execute(
            "INSERT INTO core.order_items SELECT shop_key,order_id,'duplicate',sku,"
            "quantity,unit_price,status,source_document_id "
            "FROM core.order_items"
        )
        conn.execute(
            "INSERT INTO core.returns VALUES (%s,'r1','order-1',"
            "'2026-10-29T01:00:00Z','private','requested',0,'document-1')",
            (SHOPS[0],),
        )
        conn.execute(
            "INSERT INTO core.returns SELECT shop_key,'r2',order_id,requested_at,"
            "reason,status,refund_amount,source_document_id "
            "FROM core.returns"
        )
        conn.execute(
            "INSERT INTO core.reviews VALUES (%s,'review-1','order-1','sku',"
            "'2026-10-29T01:00:00Z',1,'size private body','document-1')",
            (SHOPS[0],),
        )
    for index, shop in enumerate(SHOPS, 1):
        with psycopg.connect(database.settings.shops[shop].query_dsn.get_secret_value()) as conn:
            rows = conn.execute(
                "SELECT sku,order_id,has_return FROM mcp_data.agent_order_cohorts_v1"
            ).fetchall()
            assert rows == [("sku", f"order-{index}", index == 1)]
            assert conn.execute("SELECT * FROM mcp_data.agent_snapshot_v1").fetchall() == []
            reviews = conn.execute(
                "SELECT review_id,negative_rating,sizing_mentions "
                "FROM mcp_data.agent_review_facts_v1"
            ).fetchall()
            assert reviews == ([("review-1", True, True)] if index == 1 else [])
            columns = [
                column.name
                for column in conn.execute(
                    "SELECT * FROM mcp_data.agent_review_facts_v1 LIMIT 0"
                ).description
            ]
            assert "body" not in columns
            assert "shop_key" not in columns


def test_publication_requires_success_and_matching_revision(pipeline_database):  # noqa: F811
    from uuid import uuid4

    database, dsn, _ = pipeline_database
    run = uuid4()
    query_dsn = database.settings.shops[SHOPS[0]].query_dsn.get_secret_value()
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "INSERT INTO sync.runs(run_id,actor,idempotency_key,intent_hash,trigger,status) "
                "VALUES (%s,'test',%s,'hash','manual','running')",
                (run, str(run)),
            )
            conn.execute("UPDATE sync.state SET revision=7,last_run_id=%s", (run,))
        for status, revision, finished, visible in (
            ("running", 7, None, False),
            ("failed", 7, "2026-10-31T01:00:00Z", False),
            ("succeeded", 6, "2026-10-31T01:00:00Z", False),
            ("succeeded", 7, None, False),
            ("succeeded", 7, "2026-10-31T01:00:00Z", True),
        ):
            with psycopg.connect(dsn) as conn:
                conn.execute(
                    "UPDATE sync.runs SET "
                    "status=%s,applied_revision=%s,finished_at=%s WHERE run_id=%s",
                    (status, revision, finished, run),
                )
            with psycopg.connect(query_dsn) as conn:
                rows = conn.execute(
                    "SELECT source_revision,published_at::text,analysis_as_of::text "
                    "FROM mcp_data.agent_snapshot_v1"
                ).fetchall()
                assert rows == (
                    [(7, "2026-10-31 01:00:00+00", "2026-10-30 17:00:00+00")] if visible else []
                )
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute("UPDATE sync.state SET revision=-1,last_run_id=NULL")
            conn.execute("DELETE FROM sync.runs WHERE run_id=%s", (run,))


def test_zero_unknown_skus_dates_cutoffs_and_review_flags(pipeline_database):  # noqa: F811
    from datetime import date

    database, dsn, _ = pipeline_database
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO core.products VALUES (%s,'zero','Zero',10,'known','document-1')",
            (SHOPS[0],),
        )
        for name, ordered, updated, status in (
            ("before", "2026-10-28T16:59:59Z", "2026-10-29T00:00:00Z", "shipped"),
            ("start", "2026-10-28T17:00:00Z", "2026-10-30T17:00:00Z", "completed"),
            ("end", "2026-10-29T16:59:59Z", "2026-10-30T00:00:00Z", "completed"),
            ("next", "2026-10-29T17:00:00Z", "2026-10-30T00:00:00Z", "shipped"),
            ("cutoff", "2026-10-30T17:00:00Z", "2026-10-30T17:00:00Z", "completed"),
            ("late", "2026-10-29T00:00:00Z", "2026-10-30T17:00:01Z", "completed"),
            ("open", "2026-10-29T00:00:00Z", "2026-10-29T00:00:00Z", "open"),
        ):
            conn.execute(
                "INSERT INTO core.orders VALUES "
                "(%s,%s,%s,%s,'VND',%s,'TEST',0,0,NULL,'document-1','document-1')",
                (SHOPS[0], name, ordered, updated, status),
            )
            conn.execute(
                "INSERT INTO core.order_items VALUES "
                "(%s,%s,'line','sku',1,100,'completed','document-1')",
                (SHOPS[0], name),
            )
        for name, order, requested in (
            ("edge1", "start", "2026-10-30T16:59:59Z"),
            ("edge2", "end", "2026-10-30T17:00:00Z"),
            ("edge3", "next", "2026-10-30T17:00:01Z"),
        ):
            conn.execute(
                "INSERT INTO core.returns VALUES "
                "(%s,%s,%s,%s,'private','requested',0,'document-1')",
                (SHOPS[0], name, order, requested),
            )
        for name, rating, body, timestamp in (
            ("a", 1, "SIZE private", "2026-10-28T16:59:59Z"),
            ("b", 2, "chật", "2026-10-28T17:00:00Z"),
            ("c", 2, "nhỏ", "2026-10-29T16:59:59Z"),
            ("d", 1, "bad delivery", "2026-10-29T17:00:00Z"),
            ("e", 3, "size", "2026-10-29T00:00:00Z"),
            ("f", 2, "size", "2026-10-30T17:00:00Z"),
        ):
            conn.execute(
                "INSERT INTO core.reviews VALUES (%s,%s,'order-1','sku',%s,%s,%s,'document-1')",
                (SHOPS[0], name, timestamp, rating, body),
            )
    with psycopg.connect(database.settings.shops[SHOPS[0]].query_dsn.get_secret_value()) as conn:
        for sku, known in (("zero", True), ("unknown", False)):
            assert (
                bool(
                    conn.execute(
                        "SELECT sku FROM mcp_data.agent_sku_catalog_v1 WHERE sku=%s", (sku,)
                    ).fetchall()
                )
                is known
            )
            assert conn.execute(
                "SELECT count(*) FROM mcp_data.agent_order_cohorts_v1 WHERE sku=%s", (sku,)
            ).fetchone() == (0,)
        assert conn.execute(
            "SELECT order_id,business_date,has_return FROM "
            "mcp_data.agent_order_cohorts_v1 WHERE order_id <> 'order-1' ORDER BY order_id"
        ).fetchall() == [
            ("before", date(2026, 10, 28), False),
            ("end", date(2026, 10, 29), False),
            ("next", date(2026, 10, 30), False),
            ("start", date(2026, 10, 29), True),
        ]
        cursor = conn.execute(
            "SELECT * FROM mcp_data.agent_review_facts_v1 WHERE review_id <> "
            "'review-1' ORDER BY review_id"
        )
        assert [c.name for c in cursor.description] == [
            "sku",
            "business_date",
            "review_id",
            "source_document_id",
            "negative_rating",
            "sizing_mentions",
        ]
        assert cursor.fetchall() == [
            ("sku", date(2026, 10, 28), "a", "document-1", True, True),
            ("sku", date(2026, 10, 29), "b", "document-1", True, True),
            ("sku", date(2026, 10, 29), "c", "document-1", True, True),
            ("sku", date(2026, 10, 30), "d", "document-1", True, False),
            ("sku", date(2026, 10, 29), "e", "document-1", False, False),
        ]


def test_projection_base_tables_writes_and_cross_shop_are_denied(pipeline_database):  # noqa: F811
    import pytest
    from psycopg import sql

    from app.settings import Catalog

    database, _, roles = pipeline_database
    with psycopg.connect(
        database.settings.shops[SHOPS[1]].query_dsn.get_secret_value(), autocommit=True
    ) as conn:
        conn.execute("SELECT set_config('app.shop_key',%s,false)", (SHOPS[0],))
        assert conn.execute("SELECT order_id FROM mcp_data.agent_order_cohorts_v1").fetchall() == [
            ("order-2",)
        ]
        assert conn.execute("SELECT * FROM mcp_data.agent_review_facts_v1").fetchall() == []
        assert conn.execute("SELECT sku FROM mcp_data.agent_sku_catalog_v1").fetchall() == [
            ("sku",)
        ]
        for table in (
            "core.orders",
            "core.reviews",
            "raw.documents",
            "sync.state",
            "sync.runs",
            "mart.settings",
            "mcp_access.shop_roles",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql.SQL("SELECT * FROM {}").format(sql.SQL(table)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(roles[SHOPS[0]])))
        for dataset in Catalog.model_validate_json(
            Path("catalog.agent.example.json").read_text()
        ).datasets:
            for privilege in ("INSERT", "UPDATE", "DELETE"):
                assert conn.execute(
                    "SELECT has_table_privilege(current_user,%s,%s)", (dataset.relation, privilege)
                ).fetchone() == (False,)


def test_sdk_uses_approved_projections_and_cleans_up(pipeline_database):  # noqa: F811
    import asyncio

    from app.auth import Identity, principal
    from app.service import DataService
    from app.settings import Catalog
    from tests.test_protocol import sdk_session, tool_payload

    settings = pipeline_database[0].settings.model_copy(deep=True)
    settings.datasets = Catalog.model_validate_json(
        Path("catalog.agent.example.json").read_text()
    ).datasets
    for shop in settings.shops.values():
        shop.datasets = [d.id for d in settings.datasets]
    service = DataService(settings)

    async def exercise():
        identity = Identity(subject="+84900000001", shops={SHOPS[0]}, scopes={"data:read"})
        async with sdk_session(service, identity) as session:
            result = await session.call_tool(
                "query_mart",
                {
                    "shop_key": SHOPS[0],
                    "query": "SELECT sku FROM agent_sku_catalog_v1 WHERE sku='sku'",
                },
            )
            assert not result.is_error
            payload = tool_payload(result)
            assert payload["preview"] == [{"sku": "sku"}]
            saved = await session.call_tool(
                "read_result", {"shop_key": SHOPS[0], "result_id": payload["result_id"]}
            )
            assert not saved.is_error
            assert tool_payload(saved)["rows"] == payload["preview"]
            denied = await session.call_tool(
                "query_mart", {"shop_key": SHOPS[1], "query": "SELECT * FROM agent_sku_catalog_v1"}
            )
            assert denied.is_error
        assert principal.get(None) is None

    asyncio.run(exercise())
