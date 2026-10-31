from fastapi import FastAPI, Request
from psycopg import sql
from pydantic import BaseModel, ValidationError, create_model

from app.api.common import APIError
from app.domain.entities import RESOURCES, Record, Resource
from app.storage import entities as store
from app.storage.db import connect
from app.storage.mutations import mutate


class Result[T](BaseModel):
    data: T
    source_revision: int


class Page[T](BaseModel):
    data: list[T]
    pagination: dict[str, int]
    source_revision: int


def register_resource(app: FastAPI, resource: Resource) -> None:
    prefix = "/v1/admin/entities" if resource.admin else "/v1/entities"
    path = f"{prefix}/{resource.name}"
    model = resource.model
    key_model = create_model(
        f"{model.__name__}Key",
        __base__=Record,
        **{k: (model.model_fields[k].rebuild_annotation(), ...) for k in resource.keys},
    )
    patch_model = create_model(
        f"{model.__name__}Patch",
        __base__=Record,
        **{
            k: (f.rebuild_annotation() | None, None)
            for k, f in model.model_fields.items()
            if k not in (*resource.keys, *resource.immutable)
        },
    )

    def actor(request: Request) -> str:
        if resource.admin:
            return "admin"
        value = request.headers.get("X-Demo-User-Id", "")
        with connect() as conn:
            store.access(conn, value)
        return value

    def keys(request: Request) -> dict:
        try:
            return key_model.model_validate(dict(request.query_params)).model_dump()
        except ValidationError:
            raise APIError(422, "INVALID_RECORD_KEY") from None

    def listing(request: Request, limit: int = 50, offset: int = 0) -> dict:
        identity = actor(request)
        if not 1 <= limit <= 200 or offset < 0:
            raise APIError(422, "INVALID_PAGINATION")
        filters = {k: v for k, v in request.query_params.items() if k not in {"limit", "offset"}}
        if set(filters) - {"shop_key"} or (filters and "shop_key" not in model.model_fields):
            raise APIError(422, "INVALID_FILTER")
        with connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            # The demo is bounded; filter authorization before pagination and totals.
            rows = conn.execute(
                sql.SQL("SELECT * FROM {} WHERE deleted_at IS NULL ORDER BY {}").format(
                    sql.Identifier("mock", resource.table),
                    sql.SQL(",").join(map(sql.Identifier, resource.keys)),
                )
            ).fetchall()
            visible = []
            for value in rows:
                value = {k: value[k] for k in model.model_fields}
                if any(value.get(k) != v for k, v in filters.items()):
                    continue
                try:
                    store.authorize(conn, resource, identity, value)
                except APIError as exc:
                    if exc.status == 404:
                        continue
                    raise
                visible.append(value)
            revision = conn.execute("SELECT revision FROM mock.state").fetchone()["revision"]
        return {
            "data": visible[offset : offset + limit],
            "source_revision": revision,
            "pagination": {"limit": limit, "offset": offset, "total": len(visible)},
        }

    def get_record(request: Request) -> dict:
        identity, key = actor(request), keys(request)
        with connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            value = store.row(conn, resource, key)
            store.authorize(conn, resource, identity, value)
            revision = conn.execute("SELECT revision FROM mock.state").fetchone()["revision"]
        return {"data": value, "source_revision": revision}

    def create(request: Request, body: model) -> dict:
        identity = actor(request)
        data = body.model_dump()
        with connect() as conn:
            store.authorize(conn, resource, identity, data)

        def operation(conn, revision):
            store.authorize(conn, resource, identity, data)
            return store.save(conn, resource, data)

        return mutate(
            identity,
            request.headers.get("Idempotency-Key", ""),
            {
                "method": "POST",
                "resource": resource.name,
                "body": body.model_dump(mode="json"),
            },
            operation,
        )

    def patch(request: Request, body: patch_model) -> dict:
        identity, key = actor(request), keys(request)
        if not resource.admin:
            with connect() as conn:
                previous = store.row(conn, resource, key, include_deleted=True)
                store.authorize(conn, resource, identity, previous)

        def operation(conn, revision):
            previous = store.row(conn, resource, key)
            store.authorize(conn, resource, identity, previous)
            try:
                value = model.model_validate(previous | body.model_dump(exclude_unset=True))
            except ValidationError:
                raise APIError(422, "VALIDATION_ERROR") from None
            return store.save(conn, resource, value.model_dump(), key)

        return mutate(
            identity,
            request.headers.get("Idempotency-Key", ""),
            {
                "method": "PATCH",
                "resource": resource.name,
                "key": key_model.model_validate(key).model_dump(mode="json"),
                "body": body.model_dump(mode="json", exclude_unset=True),
            },
            operation,
        )

    def remove(request: Request) -> dict:
        identity, key = actor(request), keys(request)
        if not resource.admin:
            with connect() as conn:
                previous = store.row(conn, resource, key, include_deleted=True)
                store.authorize(conn, resource, identity, previous)

        def operation(conn, revision):
            value = store.row(conn, resource, key)
            store.authorize(conn, resource, identity, value)
            return store.delete(conn, resource, key, revision)

        return mutate(
            identity,
            request.headers.get("Idempotency-Key", ""),
            {
                "method": "DELETE",
                "resource": resource.name,
                "key": key_model.model_validate(key).model_dump(mode="json"),
            },
            operation,
        )

    app.add_api_route(path, listing, methods=["GET"], response_model=Page[model])
    app.add_api_route(path, create, methods=["POST"], response_model=Result[model], status_code=201)
    app.add_api_route(path + "/record", get_record, methods=["GET"], response_model=Result[model])
    app.add_api_route(path + "/record", patch, methods=["PATCH"], response_model=Result[model])
    app.add_api_route(path + "/record", remove, methods=["DELETE"], response_model=Result[dict])


def register(app: FastAPI) -> None:
    for resource in RESOURCES.values():
        register_resource(app, resource)

    @app.get("/v1/access")
    def get_access(user_id: str) -> dict:
        with connect() as conn:
            return store.access(conn, user_id)
