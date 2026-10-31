from datetime import UTC, datetime

from psycopg import Connection, sql
from psycopg.types.json import Jsonb

from app.api.common import APIError
from app.domain import platforms
from app.domain.entities import RESOURCES, Resource


def predicate(values: dict) -> tuple[sql.Composed, list]:
    return sql.SQL(" AND ").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in values), list(
        values.values()
    )


def row(conn: Connection, resource: Resource, keys: dict, *, include_deleted: bool = False) -> dict:
    where, params = predicate(keys)
    found = conn.execute(
        sql.SQL("SELECT * FROM {} WHERE {} {}").format(
            sql.Identifier("mock", resource.table),
            where,
            sql.SQL("") if include_deleted else sql.SQL("AND deleted_at IS NULL"),
        ),
        params,
    ).fetchone()
    if not found:
        raise APIError(404, "NOT_FOUND")
    return {k: found[k] for k in resource.model.model_fields}


def access(conn: Connection, user_id: str) -> dict:
    user = conn.execute(
        "SELECT 1 FROM mock.users WHERE user_id=%s AND is_active AND deleted_at IS NULL",
        (user_id,),
    ).fetchone()
    if not user:
        raise APIError(403, "ACCESS_DENIED")
    merchants = conn.execute(
        "SELECT m.merchant_id FROM mock.merchants m "
        "JOIN mock.merchant_memberships a USING(merchant_id) "
        "WHERE a.user_id=%s AND a.is_active AND m.is_active "
        "AND a.deleted_at IS NULL AND m.deleted_at IS NULL ORDER BY m.merchant_id",
        (user_id,),
    ).fetchall()
    merchant_ids = [m["merchant_id"] for m in merchants]
    shops = conn.execute(
        "SELECT shop_key FROM mock.shops WHERE merchant_id=ANY(%s) "
        "AND deleted_at IS NULL ORDER BY shop_key",
        (merchant_ids,),
    ).fetchall()
    return {
        "user_id": user_id,
        "merchant_ids": merchant_ids,
        "shop_keys": [s["shop_key"] for s in shops],
    }


def authorize(conn: Connection, resource: Resource, actor: str, value: dict) -> None:
    if resource.admin:
        return
    grants = access(conn, actor)
    merchant_id = value.get("merchant_id")
    if resource.table != "shops":
        shop = row(conn, RESOURCES["shops"], {"shop_key": value["shop_key"]})
        merchant_id = shop["merchant_id"]
    if merchant_id not in grants["merchant_ids"]:
        raise APIError(404, "NOT_FOUND")


def validate_refs(conn: Connection, resource: Resource, value: dict) -> None:
    for fields, target, target_fields in resource.refs:
        keys = dict(zip(target_fields, (value[f] for f in fields), strict=True))
        if any(v is None for v in keys.values()):
            continue
        where, params = predicate(keys)
        if not conn.execute(
            sql.SQL("SELECT 1 FROM {} WHERE {} AND deleted_at IS NULL").format(
                sql.Identifier("mock", target), where
            ),
            params,
        ).fetchone():
            raise APIError(409, "REFERENCE_CONFLICT")


def save(conn: Connection, resource: Resource, data: dict, keys: dict | None = None) -> dict:
    validate_refs(conn, resource, data)
    platforms.validate(conn, resource.table, data)
    table = sql.Identifier("mock", resource.table)
    values = [Jsonb(v) if isinstance(v, dict) else v for v in data.values()]
    if keys is None:
        conn.execute(
            sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                table,
                sql.SQL(",").join(map(sql.Identifier, data)),
                sql.SQL(",").join(sql.Placeholder() for _ in data),
            ),
            values,
        )
    else:
        where, params = predicate(keys)
        conn.execute(
            sql.SQL("UPDATE {} SET {} WHERE {} AND deleted_at IS NULL").format(
                table,
                sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in data),
                where,
            ),
            values + params,
        )
    platforms.aggregate(conn, resource.table, data)
    return resource.model.model_validate(data).model_dump(mode="json")


def delete(conn: Connection, resource: Resource, keys: dict, revision: int) -> dict:
    value = row(conn, resource, keys)
    for child in RESOURCES.values():
        for fields, target, target_fields in child.refs:
            if target != resource.table:
                continue
            where, params = predicate(
                dict(zip(fields, (value[f] for f in target_fields), strict=True))
            )
            dependents = conn.execute(
                sql.SQL("SELECT * FROM {} WHERE {} AND deleted_at IS NULL").format(
                    sql.Identifier("mock", child.table), where
                ),
                params,
            ).fetchall()
            if dependents:
                if resource.table != "orders":
                    raise APIError(409, "REFERENCE_CONFLICT")
                for dependent in dependents:
                    delete(conn, child, {k: dependent[k] for k in child.keys}, revision)
    where, params = predicate(keys)
    assignments = sql.SQL("deleted_at=%s")
    if "is_active" in resource.model.model_fields:
        assignments += sql.SQL(", is_active=false")
    conn.execute(
        sql.SQL("UPDATE {} SET {} WHERE {}").format(
            sql.Identifier("mock", resource.table), assignments, where
        ),
        [datetime.now(UTC), *params],
    )
    scope = {k: value[k] for k in ("merchant_id", "shop_key") if k in value}
    if "shop_key" in value and "merchant_id" not in scope:
        scope["merchant_id"] = row(conn, RESOURCES["shops"], {"shop_key": value["shop_key"]})[
            "merchant_id"
        ]
    conn.execute(
        "INSERT INTO mock.tombstones (revision,resource,record_key,scope) VALUES (%s,%s,%s,%s)",
        (
            revision,
            resource.name,
            Jsonb(
                resource.model.model_validate(value).model_dump(
                    mode="json", include=set(resource.keys)
                )
            ),
            Jsonb(scope),
        ),
    )
    key_json = resource.model.model_validate(value).model_dump(
        mode="json", include=set(resource.keys)
    )
    platforms.aggregate(conn, resource.table, value)
    return {"resource": resource.name, "key": key_json, "deleted": True}
