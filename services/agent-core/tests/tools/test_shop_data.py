"""Reject incompatible catalog contracts before querying business data."""

import pytest

from app.tools.shop_data import validate_catalog


def test_legacy_period_catalog_is_not_sku_date_compatible():
    with pytest.raises(ValueError, match="incompatible data catalog"):
        validate_catalog(
            {
                "datasets": [
                    {"id": "shop_window_metrics", "columns": ["period", "return_rate"]},
                    {"id": "product_review_metrics", "columns": ["sku", "period"]},
                ]
            }
        )


def test_missing_catalog_is_unavailable_not_empty_business_data():
    with pytest.raises(ValueError, match="incompatible data catalog"):
        validate_catalog({"datasets": []})


def approved_catalog():
    return {
        "datasets": [
            {"id": key, "relation": f"mcp_data.{key}", "layer": "mart", "columns": columns}
            for key, columns in {
                "agent_snapshot_v1": ["source_revision", "published_at", "analysis_as_of"],
                "agent_sku_catalog_v1": ["sku"],
                "agent_order_cohorts_v1": ["sku", "order_id", "business_date", "has_return"],
                "agent_review_facts_v1": [
                    "sku",
                    "business_date",
                    "review_id",
                    "source_document_id",
                    "negative_rating",
                    "sizing_mentions",
                ],
            }.items()
        ]
    }


def test_approved_sanitized_catalog_is_compatible():
    validate_catalog(approved_catalog())


@pytest.mark.parametrize("mutation", ["raw", "body", "duplicate", "relation", "missing"])
def test_rejects_unsafe_or_ambiguous_projection(mutation):
    catalog = approved_catalog()
    entry = catalog["datasets"][-1]
    if mutation == "raw":
        entry["layer"] = "raw"
    elif mutation == "body":
        entry["columns"].append("body")
    elif mutation == "duplicate":
        catalog["datasets"].append(entry.copy())
    elif mutation == "relation":
        entry["relation"] = "core.reviews"
    else:
        entry["columns"].remove("review_id")
    with pytest.raises(ValueError, match="incompatible data catalog"):
        validate_catalog(catalog)


def test_coverage_requires_baseline_and_full_local_end_day():
    from app.tools.shop_data import validate_coverage

    validate_coverage("2026-10-20", "2026-10-21", "2026-10-18", "2026-10-22T00:00:00+07:00")
    with pytest.raises(ValueError, match="incomplete coverage"):
        validate_coverage("2026-10-20", "2026-10-21", "2026-10-19", "2026-10-22T00:00:00+07:00")
    with pytest.raises(ValueError, match="incomplete coverage"):
        validate_coverage("2026-10-20", "2026-10-21", "2026-10-18", "2026-10-21T23:59:59+07:00")


@pytest.mark.parametrize("cutoff", ["2026-10-22", "2026-10-22T00:00:00", "invalid"])
def test_coverage_rejects_missing_timezone(cutoff):
    from app.tools.shop_data import validate_coverage

    with pytest.raises(ValueError):
        validate_coverage("2026-10-20", "2026-10-21", "2026-10-18", cutoff)
