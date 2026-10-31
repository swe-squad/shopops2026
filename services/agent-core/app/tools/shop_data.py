"""Contract gate for the opt-in shop-data-read-v1 profile.

This gate checks advertised projection shape only; it does not establish database
isolation or publication completeness and does not activate a runtime profile.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

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
