from fastapi import Request

from app.api.common import APIError


def current_access(request: Request) -> dict:
    identity = request.headers.get("X-Demo-User-Id", "")
    if not identity:
        raise APIError(403, "ACCESS_DENIED")
    return request.app.state.source.access(identity)


def writable(resource, grants: dict, value: dict) -> None:
    if resource.name == "shops" and "merchant_id" in value:
        allowed = value["merchant_id"] in grants["merchant_ids"]
    else:
        allowed = value.get("shop_key") in grants["shop_keys"]
    if not allowed:
        raise APIError(404, "NOT_FOUND")


def visible_shops(conn, grants: dict) -> list[str]:
    rows = conn.execute(
        "SELECT shop_key FROM core.shops WHERE shop_key=ANY(%s) AND merchant_id=ANY(%s)",
        (grants["shop_keys"], grants["merchant_ids"]),
    ).fetchall()
    return [r["shop_key"] for r in rows]
