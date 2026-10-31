from decimal import Decimal

from app.pipeline.publish import publish
from app.storage.db import connect
from app.storage.migrations import migrate
from tests.test_normalization import full_snapshot


def test_financial_and_window_regressions(database):
    migrate()
    publish(full_snapshot())
    with connect() as conn:
        assert conn.execute("SELECT count(*) n FROM core.order_items").fetchone()["n"] == 1400
        assert conn.execute("SELECT count(*) n FROM mart.shop_daily").fetchone()["n"] == 56
        counts = conn.execute(
            "SELECT shop_key,count(*) n FROM mart.issue_candidates GROUP BY 1"
        ).fetchall()
        assert {r["shop_key"]: r["n"] for r in counts} == {
            "shopee-open-platform:1001": 10,
            "lazada:1001": 10,
            "shopify:1001": 9,
        }
        economics = conn.execute(
            "SELECT * FROM mart.order_economics WHERE shop_key='lazada:1001' AND order_id='100000'"
        ).fetchone()
        assert economics["gross_sales"] == 400000
        assert economics["contribution_margin"] == 92000
        rates = conn.execute(
            "SELECT * FROM mart.shop_window_metrics "
            "WHERE shop_key='lazada:1001' AND period='recent'"
        ).fetchone()
        assert rates["orders"] == 48
        assert rates["cancellation_rate"] == Decimal("0.25")
        assert rates["effective_fee_rate"] == Decimal("0.15")
        conn.execute("UPDATE core.products SET unit_cost=NULL WHERE shop_key='lazada:1001'")
        result = conn.execute(
            "SELECT * FROM mart.order_economics WHERE shop_key='lazada:1001' AND order_id='100000'"
        ).fetchone()
        assert result["contribution_margin"] is None and not result["financials_complete"]
