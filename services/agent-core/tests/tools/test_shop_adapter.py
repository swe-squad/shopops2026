import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.tools.client import ClientError
from app.tools.shop_data import PROJECTIONS, ShopDataAdapter
from tests.tools.test_shop_binding import binding


class QueryClient:
    def __init__(self):
        self.calls = []
        self.mutation = None

    async def call_shop_tool(self, url, phone, name, arguments):
        self.calls.append((url, phone, name, arguments))
        row = {
            "known_sku": "SHIRT-M",
            "source_revision": 3,
            "published_at": "2026-10-31T00:00:00+00:00",
            "analysis_as_of": "2026-11-01T00:00:00+00:00",
            "orders": 20,
            "returns": 3,
            "baseline_orders": 20,
            "baseline_returns": 1,
        }
        result = {
            "shop_key": "shopee-open-platform:1001",
            "result_id": "a" * 32,
            "columns": list(row),
            "preview": [row],
            "truncated": False,
            "input_truncated": False,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat(),
            "provenance": {
                "queried_at": datetime.now(UTC).isoformat(),
                "catalog": [
                    {
                        "id": key,
                        "relation": "mcp_data." + key,
                        "layer": "mart",
                        "columns": sorted(cols),
                    }
                    for key, cols in PROJECTIONS.items()
                    if key != "agent_review_facts_v1"
                ],
            },
        }
        if self.mutation:
            self.mutation(result)
        return result


def execute(client, sku="SHIRT-M"):
    return asyncio.run(
        ShopDataAdapter(client).execute(
            "http://127.0.0.1:8000/mcp",
            binding(),
            "get_return_metrics",
            {"sku": sku, "start_date": "2026-10-24", "end_date": "2026-10-30"},
        )
    )


def test_metrics_are_percentages_with_real_provenance_and_selected_shop():
    client = QueryClient()
    value = execute(client)
    assert value["data"]["return_rate"] == 15
    assert value["data"]["baseline"]["return_rate"] == 5
    assert value["data"]["change_percentage_points"] == 10
    assert all("fixture:" not in s["reference"] for s in value["sources"])
    assert all(
        call[2] == "query_mart" and call[3]["shop_key"] == binding().shop_key
        for call in client.calls
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("truncated", True),
        ("input_truncated", True),
        ("shop_key", "other"),
        ("expires_at", "2000-01-01T00:00:00Z"),
        ("preview", []),
    ],
)
def test_rejects_incomplete_or_unowned_data(field, value):
    client = QueryClient()
    client.mutation = lambda result: result.update({field: value})
    with pytest.raises(ClientError):
        execute(client)


def test_sku_injection_rejected_before_network():
    client = QueryClient()
    with pytest.raises(ClientError):
        execute(client, "sku' OR TRUE --")
    assert not client.calls


@pytest.mark.parametrize("bad", [True, "20", -1, 1.5])
def test_rejects_non_integer_or_negative_counts(bad):
    client = QueryClient()
    client.mutation = lambda result: result["preview"][0].update(orders=bad)
    with pytest.raises(ClientError):
        execute(client)


class ReviewClient(QueryClient):
    def __init__(self, mixed=False):
        super().__init__()
        self.mixed = mixed

    async def call_shop_tool(self, url, phone, name, arguments):
        value = await super().call_shop_tool(url, phone, name, arguments)
        row = value["preview"][0]
        marker = {k: row[k] for k in ("source_revision", "published_at", "analysis_as_of")}
        query = arguments["query"]
        keys = ["agent_snapshot_v1", "agent_review_facts_v1"]
        if "COUNT(" in query:
            row = {**marker, "known_sku": "SHIRT-M", "negative_rating": 1, "sizing_mentions": 0}
            keys.append("agent_sku_catalog_v1")
            rows = [row]
        elif "LIMIT 20" in query:
            row = {
                **marker,
                "review_id": "r1",
                "source_document_id": "doc1",
                "business_date": "2026-10-25",
            }
            rows = [] if "f.sizing_mentions" in query else [row]
        else:
            row = marker
            if self.mixed:
                row["source_revision"] += 1
            rows = [row]
            keys = ["agent_snapshot_v1"]
        value.update(columns=list(row), preview=rows)
        value["provenance"]["catalog"] = [
            {
                "id": key,
                "relation": "mcp_data." + key,
                "layer": "mart",
                "columns": sorted(PROJECTIONS[key]),
            }
            for key in keys
        ]
        return value


def reviews(client):
    return asyncio.run(
        ShopDataAdapter(client).execute(
            "http://127.0.0.1:8000/mcp",
            binding(),
            "get_review_summary",
            {"sku": "SHIRT-M", "start_date": "2026-10-24", "end_date": "2026-10-30"},
        )
    )


def test_review_samples_are_safe_and_empty_category_still_checks_publication():
    client = ReviewClient()
    value = reviews(client)
    assert value["data"]["categories"][0]["count"] == 1
    assert len(value["data"]["categories"][0]["evidence"]) == 1
    assert value["data"]["categories"][1]["evidence"] == []
    assert len(client.calls) == 4


def test_empty_review_sample_does_not_hide_changed_publication():
    with pytest.raises(ClientError):
        reviews(ReviewClient(mixed=True))


def test_sizing_count_cannot_exceed_negative_count():
    class Impossible(ReviewClient):
        async def call_shop_tool(self, *args):
            result = await super().call_shop_tool(*args)
            if "COUNT(" in args[3]["query"]:
                result["preview"][0].update(negative_rating=0, sizing_mentions=1)
            elif "LIMIT 20" in args[3]["query"]:
                if "f.negative_rating" in args[3]["query"]:
                    result["preview"] = []
                else:
                    result["preview"] = [
                        {
                            "source_revision": 3,
                            "published_at": "2026-10-31T00:00:00+00:00",
                            "analysis_as_of": "2026-11-01T00:00:00+00:00",
                            "business_date": "2026-10-25",
                            "review_id": "r1",
                            "source_document_id": "doc1",
                        }
                    ]
            return result

    with pytest.raises(ClientError):
        reviews(Impossible())
