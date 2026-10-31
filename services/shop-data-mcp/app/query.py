"""Small, fail-closed PostgreSQL SELECT dialect over catalog projections."""

import re

from sqlglot import exp, parse

from app.settings import Dataset

ALLOWED = {
    "Select",
    "From",
    "Table",
    "Identifier",
    "Column",
    "Alias",
    "TableAlias",
    "Literal",
    "Null",
    "Boolean",
    "Star",
    "Where",
    "Group",
    "Having",
    "Order",
    "Ordered",
    "Limit",
    "Offset",
    "Join",
    "Paren",
    "And",
    "Or",
    "Not",
    "EQ",
    "NEQ",
    "GT",
    "GTE",
    "LT",
    "LTE",
    "Is",
    "In",
    "Between",
    "Like",
    "ILike",
    "Add",
    "Sub",
    "Mul",
    "Div",
    "Mod",
    "Neg",
    "Distinct",
    "Case",
    "If",
    "Count",
    "Sum",
    "Avg",
    "Min",
    "Max",
    "Round",
    "Abs",
    "Coalesce",
    "Nullif",
    "Lower",
    "Upper",
    "Cast",
    "DataType",
    "DataTypeParam",
    "Extract",
}


def compile_query(
    query: str,
    datasets: list[Dataset],
    grant: dict | None = None,
    temporary: dict[str, dict] | None = None,
) -> str:
    if len(query) > 20000:
        raise ValueError("Query too long")
    try:
        statements = parse(query, read="postgres")
    except Exception:
        raise ValueError("Invalid query") from None
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError("One SELECT statement is required")
    tree = statements[0]
    for node in tree.walk():
        if isinstance(node, exp.Identifier) and not re.fullmatch(
            r"[a-z][a-z0-9_]{0,62}", node.name
        ):
            raise ValueError("Use simple lowercase identifiers and aliases")
        if type(node).__name__ not in ALLOWED:
            raise ValueError(f"Unsupported SQL construct: {type(node).__name__}")
        if isinstance(node, exp.DataType) and node.sql().upper() not in {
            "TEXT",
            "INT",
            "BIGINT",
            "DOUBLE",
            "DECIMAL",
            "BOOLEAN",
            "DATE",
            "TIMESTAMP",
            "TIMESTAMPTZ",
            "VARCHAR",
        }:
            raise ValueError("Unsupported cast")
    tables = list(tree.find_all(exp.Table))
    if not tables:
        raise ValueError("Query must reference a catalog dataset")
    catalog = {d.id: d for d in datasets}
    for table in tables:
        name = table.name
        if table.db or table.catalog:
            raise ValueError("Use dataset IDs, not physical table names")
        alias = table.alias_or_name
        if name in (temporary or {}):
            artifact = temporary[name]
            # Typed conversion is server-generated, never part of submitted SQL.
            import json

            rows = exp.Literal.string(json.dumps(artifact["rows"]))
            if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", c) for c in artifact["columns"]):
                raise ValueError("Temporary columns need simple aliases")
            fields = ", ".join(f'"{c}" text' for c in artifact["columns"])
            source = f"jsonb_to_recordset({rows.sql(dialect='postgres')}::jsonb) AS x({fields})"
            replacement = f"SELECT * FROM {source}"
        else:
            d = catalog.get(name)
            if d is None:
                raise ValueError("Dataset unavailable")
            columns = d.columns
            condition = ""
            if d.layer == "raw":
                if not grant or name not in grant.get("datasets", {}):
                    raise ValueError("Raw grant required")
                columns = [c for c in columns if c in grant["datasets"][name]]
                if not columns or d.time_column not in d.columns:
                    raise ValueError("Raw scope unavailable")
                start = exp.Literal.string(grant["start"]).sql(dialect="postgres")
                end = exp.Literal.string(grant["end"]).sql(dialect="postgres")
                condition = (
                    f' WHERE "{d.time_column}" >= {start}::timestamptz'
                    f' AND "{d.time_column}" < {end}::timestamptz'
                )
            fields = ", ".join(f'"{c}"' for c in columns)
            schema, relation = d.relation.split(".")
            replacement = f'SELECT {fields} FROM "{schema}"."{relation}"{condition}'
        table.replace(
            exp.Subquery(
                this=exp.select("*").from_(f"({replacement}) AS protected_source"),
                alias=exp.TableAlias(this=exp.to_identifier(alias)),
            )
        )
    return tree.sql(dialect="postgres")
