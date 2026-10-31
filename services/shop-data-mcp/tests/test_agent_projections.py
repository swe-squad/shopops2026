"""T10 projections against disposable PostgreSQL, including real query logins."""

from pathlib import Path

import psycopg

from tests.test_pipeline_database import SHOPS, pipeline_database  # noqa: F401


def test_agent_projection_grain_privacy_and_isolation(pipeline_database):  # noqa: F811
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
