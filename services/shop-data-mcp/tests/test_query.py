"""Unit checks for compiler boundaries; these do not establish PostgreSQL isolation."""

import pytest
from sqlglot import exp, parse_one

from app.query import compile_query
from app.settings import Dataset


@pytest.fixture
def catalog() -> list[Dataset]:
    return [
        Dataset(
            id="orders",
            relation="analytics.order_summary",
            layer="mart",
            description="Allowed aggregate",
            columns=["status", "total"],
        ),
        Dataset(
            id="raw_orders",
            relation="source.orders",
            layer="raw",
            description="Restricted raw data",
            columns=["order_id", "status", "buyer_email", "created_at"],
            time_column="created_at",
        ),
    ]


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM orders; DELETE FROM orders",
        "DELETE FROM orders",
        "SELECT * INTO stolen FROM orders",
        "SELECT * FROM analytics.order_summary",
        "SELECT * FROM private_orders",
        "SELECT pg_read_file('/etc/passwd') FROM orders",
        "SELECT pg_sleep(10) FROM orders",
        "SELECT set_config('role', 'admin', false) FROM orders",
        "SELECT * FROM orders FOR UPDATE",
        "COPY orders TO '/tmp/orders'",
        "WITH hidden AS (SELECT * FROM orders) SELECT * FROM hidden",
        "SELECT * FROM orders UNION SELECT * FROM raw_orders",
        "SELECT CAST(status AS regclass) FROM orders",
        "SELECT * FROM pg_catalog.pg_class",
        "SELECT 1",
    ],
)
def test_disallowed_sql_fails_closed(catalog: list[Dataset], query: str) -> None:
    with pytest.raises(ValueError):
        compile_query(query, catalog)


def test_catalog_projection_is_inside_protected_relation(catalog: list[Dataset]) -> None:
    compiled = parse_one(
        compile_query("SELECT status, SUM(total) AS total FROM orders GROUP BY status", catalog),
        read="postgres",
    )
    physical = list(compiled.find_all(exp.Table))
    assert len(physical) == 1
    assert (physical[0].db, physical[0].name) == ("analytics", "order_summary")
    projection = physical[0].find_ancestor(exp.Select)
    assert [column.name for column in projection.expressions] == ["status", "total"]


def test_raw_requires_explicit_dataset_grant(catalog: list[Dataset]) -> None:
    for grant in [None, {"datasets": {"another_raw_dataset": ["order_id"]}}]:
        with pytest.raises(ValueError, match="Raw grant required"):
            compile_query("SELECT * FROM raw_orders", catalog, grant)


def test_raw_scope_projects_only_granted_columns_and_half_open_window(
    catalog: list[Dataset],
) -> None:
    grant = {
        "datasets": {"raw_orders": ["order_id", "status", "not_in_catalog"]},
        "start": "2026-10-01T00:00:00Z",
        "end": "2026-10-02T00:00:00Z",
    }
    tree = parse_one(compile_query("SELECT * FROM raw_orders", catalog, grant), read="postgres")
    source = next(tree.find_all(exp.Table)).find_ancestor(exp.Select)
    assert [item.name for item in source.expressions] == ["order_id", "status"]
    assert "buyer_email" not in source.sql()
    assert "not_in_catalog" not in source.sql()
    lower, upper = source.find(exp.GTE), source.find(exp.LT)
    assert lower.this.name == upper.this.name == "created_at"
    assert lower.expression.find(exp.Literal).this == grant["start"]
    assert upper.expression.find(exp.Literal).this == grant["end"]


def test_raw_joins_scope_each_reference(catalog: list[Dataset]) -> None:
    grant = {
        "datasets": {"raw_orders": ["order_id"]},
        "start": "2026-10-01T00:00:00Z",
        "end": "2026-10-02T00:00:00Z",
    }
    tree = parse_one(
        compile_query(
            "SELECT a.order_id FROM raw_orders a JOIN raw_orders b ON a.order_id = b.order_id",
            catalog,
            grant,
        ),
        read="postgres",
    )
    assert len(list(tree.find_all(exp.GTE))) == 2
    assert len(list(tree.find_all(exp.LT))) == 2


def test_empty_raw_projection_fails_closed(catalog: list[Dataset]) -> None:
    with pytest.raises(ValueError, match="Raw scope unavailable"):
        compile_query("SELECT * FROM raw_orders", catalog, {"datasets": {"raw_orders": []}})


def test_temporary_relation_exists_only_when_explicitly_supplied() -> None:
    with pytest.raises(ValueError, match="Dataset unavailable"):
        compile_query("SELECT * FROM temp", [])
    compiled = compile_query(
        "SELECT status FROM temp",
        [],
        temporary={"temp": {"columns": ["status"], "rows": [{"status": "ready'quoted"}]}},
    )
    tree = parse_one(compiled, read="postgres")
    assert "JSONB_TO_RECORDSET" in compiled
    assert not [
        table for table in tree.find_all(exp.Table) if isinstance(table.this, exp.Identifier)
    ]
    assert tree.find(exp.Literal).this == '[{"status": "ready\'quoted"}]'


def test_temporary_source_cannot_expose_a_second_unsupplied_relation() -> None:
    with pytest.raises(ValueError, match="Dataset unavailable"):
        compile_query(
            "SELECT * FROM temp JOIN other_saved_result ON true",
            [],
            temporary={"temp": {"columns": ["status"], "rows": []}},
        )


@pytest.mark.parametrize("column", ['v" text, "other', "status;drop", "Uppercase", "*"])
def test_temporary_schema_rejects_unsafe_or_unrepresentable_aliases(column: str) -> None:
    with pytest.raises(ValueError, match="Temporary columns need simple aliases"):
        compile_query(
            "SELECT * FROM temp",
            [],
            temporary={"temp": {"columns": [column], "rows": []}},
        )
