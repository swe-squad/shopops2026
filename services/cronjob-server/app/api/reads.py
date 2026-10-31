"""Read-only allowlists; current source access intersects processed ownership."""

from datetime import date

from fastapi import FastAPI, Request
from psycopg import sql
from pydantic import ValidationError, create_model

from app.api.auth import current_access, visible_shops
from app.api.common import APIError
from app.api.contracts import Page, Result
from app.api.derived_models import READ_MODELS, Documents, UserShopAccess
from app.source.entities import RESOURCES, Record
from app.storage.db import connect

MARTS = {
    "order_economics": ("shop_key", "order_id"),
    "shop_daily": ("shop_key", "business_date", "currency"),
    "shop_window_metrics": ("shop_key", "period", "currency"),
    "product_review_metrics": ("shop_key", "sku", "period"),
    "inventory_risk": ("shop_key", "sku"),
    "promotion_performance": ("shop_key", "promotion_id", "currency"),
    "issue_candidates": ("shop_key", "issue_key"),
    "agent_context": ("shop_key", "issue_key"),
}
TIME_FIELDS = {
    "orders": "ordered_at",
    "reviews": "reviewed_at",
    "returns": "requested_at",
    "inventory": "observed_at",
    "account_health": "occurred_at",
    "order_economics": "ordered_at",
    "shop_daily": "business_date",
    "documents": "captured_at",
}


def pagination(request: Request) -> tuple[int, int]:
    try:
        limit = int(request.query_params.get("limit", "50"))
        offset = int(request.query_params.get("offset", "0"))
        if not 1 <= limit <= 200 or offset < 0:
            raise ValueError()
        return limit, offset
    except ValueError:
        raise APIError(422, "INVALID_PAGINATION") from None


def read(request, schema, table, grain, *, record_keys=None) -> dict:
    grants = current_access(request)
    limit, offset = pagination(request)
    filters = dict(request.query_params) if record_keys is None else record_keys
    allowed = set(grain) | {"limit", "offset"}
    if schema == "raw":
        allowed.add("shop_key")
    if table in TIME_FIELDS:
        allowed |= {"date_from", "date_to"}
    if set(filters) - allowed:
        raise APIError(422, "INVALID_FILTER")
    with connect() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        shops = visible_shops(conn, grants)
        relation = sql.Identifier(schema, table)
        scope = (
            sql.SQL("r.platform || ':' || r.shop_id") if schema == "raw" else sql.SQL("r.shop_key")
        )
        where = [sql.SQL("{}=ANY(%s)").format(scope)]
        values = [shops]
        if schema == "raw":
            where.append(sql.SQL("r.merchant_id=ANY(%s)"))
            values.append(grants["merchant_ids"])
        for name, value in filters.items():
            if name in {"limit", "offset"}:
                continue
            if schema == "raw" and name == "shop_key":
                where.append(sql.SQL("{}=%s").format(scope))
            elif name in {"date_from", "date_to"}:
                try:
                    value = date.fromisoformat(value)
                except ValueError:
                    raise APIError(422, "INVALID_FILTER") from None
                operator = sql.SQL(">=") if name == "date_from" else sql.SQL("<")
                where.append(
                    sql.SQL("r.{}{}%s").format(sql.Identifier(TIME_FIELDS[table]), operator)
                )
            else:
                where.append(sql.SQL("r.{}=%s").format(sql.Identifier(name)))
            values.append(value)
        clause = sql.SQL(" AND ").join(where)
        total = conn.execute(
            sql.SQL("SELECT count(*) n FROM {} r WHERE {}").format(relation, clause), values
        ).fetchone()["n"]
        rows = conn.execute(
            sql.SQL("SELECT r.* FROM {} r WHERE {} ORDER BY {} LIMIT %s OFFSET %s").format(
                relation, clause, sql.SQL(",").join(sql.Identifier("r", k) for k in grain)
            ),
            [*values, limit, offset],
        ).fetchall()
        revision = conn.execute("SELECT revision FROM sync.state").fetchone()["revision"]
    if record_keys is not None:
        if not rows:
            raise APIError(404, "NOT_FOUND")
        return {"data": rows[0], "applied_source_revision": revision}
    return {
        "data": rows,
        "pagination": {"limit": limit, "offset": offset, "total": total},
        "applied_source_revision": revision,
    }


def register_core(app: FastAPI, resource) -> None:
    model = create_model(
        f"Core{resource.model.__name__}",
        __base__=resource.model,
        source_document_id=(str, ...),
        **({"enrichment_source_document_id": (str, ...)} if resource.name == "orders" else {}),
    )
    key_model = create_model(
        f"Core{resource.model.__name__}Key",
        __base__=Record,
        **{k: (resource.model.model_fields[k].rebuild_annotation(), ...) for k in resource.keys},
    )

    def listing(request: Request) -> dict:
        return read(request, "core", resource.table, resource.keys)

    def single(request: Request) -> dict:
        try:
            keys = key_model.model_validate(dict(request.query_params)).model_dump()
        except ValidationError:
            raise APIError(422, "INVALID_RECORD_KEY") from None
        return read(request, "core", resource.table, resource.keys, record_keys=keys)

    path = f"/v1/core/{resource.name}"
    app.add_api_route(path, listing, methods=["GET"], response_model=Page[model])
    app.add_api_route(path + "/record", single, methods=["GET"], response_model=Result[model])


def register_mart(app: FastAPI, name: str, grain: tuple[str, ...]) -> None:
    def listing(request: Request) -> dict:
        return read(request, "mart", name, grain)

    app.add_api_route(
        f"/v1/marts/{name}", listing, methods=["GET"], response_model=Page[READ_MODELS[name]]
    )


def register(app: FastAPI) -> None:
    for resource in RESOURCES.values():
        if not resource.admin:
            register_core(app, resource)
    for name, grain in MARTS.items():
        register_mart(app, name, grain)

    @app.get("/v1/raw/documents", response_model=Page[Documents])
    def documents(request: Request) -> dict:
        return read(request, "raw", "documents", ("document_id", "platform", "shop_id", "resource"))

    @app.get("/v1/raw/documents/record", response_model=Result[Documents])
    def document(request: Request, document_id: str) -> dict:
        if set(request.query_params) != {"document_id"}:
            raise APIError(422, "INVALID_RECORD_KEY")
        return read(
            request, "raw", "documents", ("document_id",), record_keys={"document_id": document_id}
        )

    @app.get("/v1/access/shops", response_model=Page[UserShopAccess])
    def shops(request: Request) -> dict:
        grants = current_access(request)
        limit, offset = pagination(request)
        if set(request.query_params) - {"limit", "offset"}:
            raise APIError(422, "INVALID_FILTER")
        with connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            allowed = visible_shops(conn, grants)
            rows = conn.execute(
                "SELECT * FROM access.user_shop_access WHERE user_id=%s "
                "AND shop_key=ANY(%s) ORDER BY shop_key",
                (grants["user_id"], allowed),
            ).fetchall()
            revision = conn.execute("SELECT revision FROM sync.state").fetchone()["revision"]
        return {
            "data": rows[offset : offset + limit],
            "pagination": {"limit": limit, "offset": offset, "total": len(rows)},
            "applied_source_revision": revision,
        }
