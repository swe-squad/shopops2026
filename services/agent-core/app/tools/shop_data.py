"""Contract gate for the opt-in shop-data-read-v1 profile.

This gate checks advertised projection shape only; it does not establish database
isolation or publication completeness and does not activate a runtime profile.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.tools.client import MCPClient
from app.tools.shop_bindings import Binding

PROJECTIONS = {
    "agent_snapshot_v1": {"source_revision", "published_at", "analysis_as_of"},
    "agent_sku_catalog_v1": {"sku"},
    "agent_order_cohorts_v1": {"sku", "order_id", "business_date", "has_return"},
    "agent_review_facts_v1": {
        "sku",
        "business_date",
        "review_id",
        "source_document_id",
        "negative_rating",
        "sizing_mentions",
    },
}


def validate_catalog(catalog: dict) -> None:
    """Reject missing, ambiguous, raw or incompatible approved projections."""
    datasets = catalog.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("incompatible data catalog")
    by_id = {}
    for dataset in datasets:
        if not isinstance(dataset, dict) or not isinstance(dataset.get("id"), str):
            raise ValueError("incompatible data catalog")
        key = dataset["id"]
        if key in by_id:
            raise ValueError("incompatible data catalog")
        by_id[key] = dataset
    for key, expected in PROJECTIONS.items():
        dataset = by_id.get(key, {})
        columns = dataset.get("columns")
        if (
            dataset.get("layer") != "mart"
            or dataset.get("relation") != f"mcp_data.{key}"
            or not isinstance(columns, list)
            or any(not isinstance(column, str) for column in columns)
            or len(columns) != len(expected)
            or set(columns) != expected
        ):
            raise ValueError("incompatible data catalog")


def validate_coverage(
    start_date: str, end_date: str, coverage_start: str, analysis_as_of: str
) -> None:
    """Require the whole requested interval and preceding baseline in demo coverage."""
    start, end, lower = map(date.fromisoformat, (start_date, end_date, coverage_start))
    days = (end - start).days + 1
    if not 1 <= days <= 90:
        raise ValueError("invalid date interval")
    cutoff = datetime.fromisoformat(analysis_as_of)
    if cutoff.tzinfo is None:
        raise ValueError("analysis cutoff requires timezone")
    try:
        baseline_start = start - timedelta(days=days)
        exclusive_end = datetime.combine(
            end + timedelta(days=1), time.min, ZoneInfo("Asia/Ho_Chi_Minh")
        )
    except OverflowError:
        raise ValueError("invalid date interval") from None
    if baseline_start < lower or exclusive_end > cutoff:
        raise ValueError("incomplete coverage")


class ShopDataAdapter:
    """Fixed bounded aggregate queries; no arbitrary SQL enters from model arguments."""

    def __init__(self, client: MCPClient) -> None:
        self.client = client

    async def execute(self, url: str, binding: Binding, name: str, arguments: dict) -> dict:
        import re

        from app.tools.client import ClientError
        from app.tools.validation import validate_arguments

        try:
            args = validate_arguments(name, arguments)
            if name not in {"get_return_metrics", "get_review_summary"} or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", args["sku"]
            ):
                raise ValueError
        except ValueError, TypeError, KeyError:
            raise ClientError("invalid_input", retryable=False) from None
        try:
            return await self._execute(url, binding, name, args)
        except ClientError:
            raise
        except ValueError, TypeError, KeyError, OverflowError, AttributeError:
            raise ClientError("upstream_unavailable", retryable=False) from None

    async def _query(
        self,
        url: str,
        binding: Binding,
        query: str,
        columns: list[str],
        datasets: list[str],
        *,
        empty: bool = False,
    ) -> tuple[list[dict], str]:
        import re
        from datetime import UTC

        from app.tools.client import ClientError

        value = await self.client.call_shop_tool(
            url, binding.phone, "query_mart", {"shop_key": binding.shop_key, "query": query}
        )
        if (
            value.get("shop_key") != binding.shop_key
            or value.get("truncated") is not False
            or value.get("input_truncated") is not False
            or not isinstance(value.get("result_id"), str)
            or not re.fullmatch(r"[a-f0-9]{32}", value["result_id"])
        ):
            raise ValueError("invalid data result")
        expiry = datetime.fromisoformat(value["expires_at"])
        if expiry.tzinfo is None or expiry <= datetime.now(UTC):
            raise ValueError("expired result")
        returned = value["columns"]
        if (
            not isinstance(returned, list)
            or len(returned) != len(columns)
            or set(returned) != set(columns)
        ):
            raise ValueError("invalid columns")
        catalog = value["provenance"]["catalog"]
        if not isinstance(catalog, list) or {item["id"] for item in catalog} != set(datasets):
            raise ValueError("missing query provenance")
        # Validate just the actual participating projections using the same closed contract.
        advertised = {item["id"]: item for item in catalog}
        if len(advertised) != len(catalog):
            raise ValueError("duplicate query provenance")
        validate_catalog(
            {
                "datasets": [
                    advertised.get(
                        key,
                        {
                            "id": key,
                            "relation": "mcp_data." + key,
                            "layer": "mart",
                            "columns": sorted(cols),
                        },
                    )
                    for key, cols in PROJECTIONS.items()
                ]
            }
        )
        queried = datetime.fromisoformat(value["provenance"]["queried_at"])
        if queried.tzinfo is None:
            raise ValueError("missing read time")
        rows = value["preview"]
        if not isinstance(rows, list) or len(rows) > 20 or (not rows and not empty):
            raise ClientError("upstream_unavailable", retryable=False)
        if any(not isinstance(row, dict) or set(row) != set(columns) for row in rows):
            raise ValueError("invalid rows")
        return rows, value["result_id"]

    async def _execute(self, url: str, binding: Binding, name: str, args: dict) -> dict:
        from app.tools.client import ClientError

        start, end = date.fromisoformat(args["start_date"]), date.fromisoformat(args["end_date"])
        baseline = start - timedelta(days=(end - start).days + 1)
        sku = args["sku"]
        metadata = "s.source_revision, s.published_at, s.analysis_as_of"
        markers = ["source_revision", "published_at", "analysis_as_of"]
        dataset = (
            "agent_order_cohorts_v1" if name == "get_return_metrics" else "agent_review_facts_v1"
        )
        sources = []
        if name == "get_return_metrics":
            fields = (
                f"COUNT(CASE WHEN f.business_date >= '{start}' THEN f.order_id END) AS orders, "
                f"COUNT(CASE WHEN f.business_date >= '{start}' AND f.has_return "
                "THEN f.order_id END) AS returns, "
                f"COUNT(CASE WHEN f.business_date < '{start}' THEN f.order_id END) "
                "AS baseline_orders, "
                f"COUNT(CASE WHEN f.business_date < '{start}' AND f.has_return "
                "THEN f.order_id END) AS baseline_returns"
            )
            counts = ["orders", "returns", "baseline_orders", "baseline_returns"]
            lower = baseline
        else:
            fields = (
                "COUNT(CASE WHEN f.negative_rating THEN f.review_id END) AS negative_rating, "
                "COUNT(CASE WHEN f.sizing_mentions THEN f.review_id END) AS sizing_mentions"
            )
            counts = ["negative_rating", "sizing_mentions"]
            lower = start
        query = (
            f"SELECT {metadata}, k.sku AS known_sku, {fields} FROM agent_snapshot_v1 s "
            f"LEFT JOIN agent_sku_catalog_v1 k ON k.sku = '{sku}' "
            f"LEFT JOIN {dataset} f ON f.sku = k.sku AND f.business_date >= '{lower}' "
            f"AND f.business_date <= '{end}' GROUP BY {metadata}, k.sku"
        )
        rows, result_id = await self._query(
            url,
            binding,
            query,
            markers + ["known_sku"] + counts,
            ["agent_snapshot_v1", "agent_sku_catalog_v1", dataset],
        )
        if len(rows) != 1:
            raise ValueError("ambiguous publication")
        row = rows[0]
        marker = self._marker(row)
        validate_coverage(str(start), str(end), binding.coverage_start, row["analysis_as_of"])
        if row["known_sku"] is None:
            raise ClientError("not_found", retryable=False)
        if row["known_sku"] != sku or any(type(row[c]) is not int or row[c] < 0 for c in counts):
            raise ValueError("invalid aggregate")

        def source(key: str, rid: str) -> dict:
            return {
                "type": "data",
                "reference": f"data:{key}:revision:{marker[0]}:asof:{marker[2]}:result:{rid}",
            }

        sources.append(source(dataset, result_id))
        if name == "get_return_metrics":

            def period(a: date, b: date, orders: int, returns: int) -> dict:
                if returns > orders:
                    raise ValueError("invalid counts")
                return {
                    "start_date": str(a),
                    "end_date": str(b),
                    "orders": orders,
                    "returns": returns,
                    "return_rate": round(returns / orders * 100, 6) if orders else None,
                }

            data = period(start, end, row["orders"], row["returns"])
            previous = period(
                baseline, start - timedelta(days=1), row["baseline_orders"], row["baseline_returns"]
            )
            change = (
                round(data["return_rate"] - previous["return_rate"], 6)
                if data["return_rate"] is not None and previous["return_rate"] is not None
                else None
            )
            data.update(
                sku=sku,
                timezone="Asia/Ho_Chi_Minh",
                baseline=previous,
                change_percentage_points=change,
            )
        else:
            import hashlib

            if row["sizing_mentions"] > row["negative_rating"]:
                raise ValueError("invalid category counts")
            categories = []
            for category in counts:
                sample_query = (
                    f"SELECT {metadata}, f.review_id, f.source_document_id, f.business_date "
                    f"FROM agent_snapshot_v1 s JOIN {dataset} f ON f.sku = '{sku}' "
                    f"WHERE f.business_date >= '{start}' AND f.business_date <= '{end}' "
                    f"AND f.{category} ORDER BY f.business_date, f.review_id LIMIT 20"
                )
                samples, rid = await self._query(
                    url,
                    binding,
                    sample_query,
                    markers + ["review_id", "source_document_id", "business_date"],
                    ["agent_snapshot_v1", dataset],
                    empty=True,
                )
                if len(samples) != min(row[category], 20):
                    raise ValueError("incomplete evidence")
                evidence = []
                seen = set()
                for sample in samples:
                    if self._marker(sample) != marker:
                        raise ValueError("mixed publications")
                    if (
                        not isinstance(sample["review_id"], str)
                        or not sample["review_id"]
                        or not isinstance(sample["source_document_id"], str)
                        or not sample["source_document_id"]
                        or not start <= date.fromisoformat(sample["business_date"]) <= end
                        or sample["review_id"] in seen
                    ):
                        raise ValueError("invalid evidence")
                    seen.add(sample["review_id"])
                    digest = hashlib.sha256(
                        (sample["source_document_id"] + "\0" + sample["review_id"]).encode()
                    ).hexdigest()
                    evidence.append(source(dataset, rid)["reference"] + ":review:" + digest)
                sources.append(source(dataset, rid))
                categories.append(
                    {"category": category, "count": row[category], "evidence": evidence}
                )
            final_rows, final_id = await self._query(
                url,
                binding,
                f"SELECT {metadata} FROM agent_snapshot_v1 s",
                markers,
                ["agent_snapshot_v1"],
            )
            if len(final_rows) != 1 or self._marker(final_rows[0]) != marker:
                raise ValueError("mixed publications")
            sources.append(source("agent_snapshot_v1", final_id))
            data = {**args, "categories": categories}
        return {
            "schema_version": "1",
            "data": data,
            "observed_at": row["published_at"],
            "sources": sources,
            "error": None,
        }

    @staticmethod
    def _marker(row: dict) -> tuple[int, str, str]:
        revision = row["source_revision"]
        if type(revision) is not int or revision < 0:
            raise ValueError("invalid revision")
        for key in ("published_at", "analysis_as_of"):
            if datetime.fromisoformat(row[key]).tzinfo is None:
                raise ValueError("invalid publication marker")
        return revision, row["published_at"], row["analysis_as_of"]
