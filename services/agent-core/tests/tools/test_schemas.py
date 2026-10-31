import json

import pytest

from app.contracts.tools import ToolResult
from app.tools.validation import definitions, validate_arguments, validate_result

DATES = {"sku": "SKU-A", "start_date": "2026-10-19", "end_date": "2026-10-25"}


def test_inclusive_ninety_days_and_same_day() -> None:
    assert validate_arguments("get_return_metrics", DATES) == DATES
    for end in ("2026-01-01", "2026-03-31"):
        validate_arguments("get_return_metrics", dict(DATES, start_date="2026-01-01", end_date=end))


@pytest.mark.parametrize(
    "patch",
    [
        {"sku": ""},
        {"sku": "x" * 65},
        {"sku": 1},
        {"start_date": "2026-10-26"},
        {"start_date": "2026-01-01", "end_date": "2026-04-01"},
        {"start_date": "20261019"},
        {"start_date": "2026-02-30"},
        {"start_date": "2026-10-19T00:00:00Z"},
    ],
)
def test_reject_bad_dates_and_sku(patch: dict) -> None:
    with pytest.raises(ValueError):
        validate_arguments("get_return_metrics", DATES | patch)


@pytest.mark.parametrize(
    "key",
    [
        "tenant_id",
        "shop_id",
        "user_id",
        "conversation_id",
        "sql",
        "path",
        "url",
        "tool_name",
        "knowledge_version",
    ],
)
def test_reject_identity_and_execution_arguments(key: str) -> None:
    with pytest.raises(ValueError):
        validate_arguments("get_return_metrics", DATES | {key: "untrusted"})


@pytest.mark.parametrize("limit", [0, 21, True, "2"])
def test_limit_is_bounded_integer(limit: object) -> None:
    with pytest.raises(ValueError):
        validate_arguments("search_knowledge", {"query": "sizing", "limit": limit})


def test_history_boundary_and_unknown_tool() -> None:
    assert validate_arguments("get_conversation_history", {"before_sequence": None, "limit": 20})
    with pytest.raises(ValueError):
        validate_arguments("get_conversation_history", {"before_sequence": 0, "limit": 1})
    with pytest.raises(ValueError):
        validate_arguments("execute_sql", {})


def test_definitions_are_closed_and_json_schemas_are_published() -> None:
    from pathlib import Path

    for definition in definitions():
        schema = definition.input_schema
        assert schema["additionalProperties"] is False
        published = json.loads(Path(f"contracts/tools/v1/{definition.name}.json").read_text())
        assert published == schema


def test_result_limit_counts_utf8_and_rejects_malformed_shape() -> None:
    with pytest.raises(ValueError):
        validate_result("search_knowledge", {"data": {"matches": []}})
    match = {
        "document_id": "sizing",
        "chunk_id": "1",
        "excerpt": "é" * 1800,
        "bundle_id": "returns-v1",
        "version": "1",
    }
    small = ToolResult(
        data={"matches": [match]}, sources=(), observed_at="2026-10-25T00:00:00Z"
    ).model_dump(mode="json")
    assert validate_result("search_knowledge", small).data["matches"][0]["excerpt"] == "é" * 1800
    # Valid shape, within 20 items and 4000 characters/excerpt, but >32KiB UTF-8.
    large = small | {"data": {"matches": [match] * 10}}
    with pytest.raises(ValueError, match="32 KiB"):
        validate_result("search_knowledge", large)
    with pytest.raises(ValueError):
        validate_result("get_return_metrics", ToolResult(data={"orders": -1}).model_dump())
    with pytest.raises(ValueError):
        validate_result("search_knowledge", {"error": "permission_denied", "data": {"leak": 1}})


def test_dates_that_cannot_represent_baseline_are_invalid() -> None:
    with pytest.raises(ValueError):
        validate_arguments(
            "get_return_metrics",
            {"sku": "SKU-A", "start_date": "0001-01-01", "end_date": "0001-01-01"},
        )


def test_metrics_baseline_must_be_immediately_previous_equal_interval() -> None:
    from app.tools.validation import validate_context
    from tests.mcp.support import config

    value = ToolResult(
        data={
            "sku": "SKU-A",
            "start_date": "2026-10-19",
            "end_date": "2026-10-25",
            "timezone": "Asia/Ho_Chi_Minh",
            "orders": 100,
            "returns": 15,
            "return_rate": 15,
            "baseline": {
                "start_date": "1990-01-01",
                "end_date": "1990-01-01",
                "orders": 100,
                "returns": 5,
                "return_rate": 5,
            },
            "change_percentage_points": 10,
        },
        sources=({"type": "data", "reference": "remote:opaque-source"},),
        observed_at="2026-10-25T00:00:00Z",
    )
    validate_result("get_return_metrics", value.model_dump(mode="json"))
    with pytest.raises(ValueError):
        validate_context("get_return_metrics", DATES, value, "conv-a", config())
