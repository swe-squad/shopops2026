from fastapi import FastAPI, Request
from pydantic import ValidationError, create_model

from app.api.auth import current_access, writable
from app.api.common import APIError
from app.api.contracts import Mutation, SourcePage, SourceResult
from app.jobs.store import accept, previous_intent, resolve_mutation
from app.source.entities import RESOURCES, Record


def register_resource(app: FastAPI, resource) -> None:
    prefix = "/v1/admin/mock" if resource.admin else "/v1/mock"
    upstream = "/v1/admin/entities" if resource.admin else "/v1/entities"
    path, source_path = f"{prefix}/{resource.name}", f"{upstream}/{resource.name}"
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

    def keys(request: Request) -> dict:
        try:
            return key_model.model_validate(dict(request.query_params)).model_dump(mode="json")
        except ValidationError:
            raise APIError(422, "INVALID_RECORD_KEY") from None

    def identity(request: Request, value=None) -> str:
        if resource.admin:
            return "admin"
        grants = current_access(request)
        if value is not None:
            writable(resource, grants, value)
        return grants["user_id"]

    def listing(request: Request, limit: int = 50, offset: int = 0) -> dict:
        return request.app.state.source.request(
            "GET", source_path, actor=identity(request), params=dict(request.query_params)
        )

    def get_record(request: Request) -> dict:
        key = keys(request)
        return request.app.state.source.request(
            "GET", source_path + "/record", actor=identity(request, key), params=key
        )

    def write(
        request: Request, method: str, body: dict | None = None, record: bool = False
    ) -> dict:
        key = keys(request) if record else {}
        authorization = None
        idempotency_key = request.headers.get("Idempotency-Key", "")
        if resource.name == "shops" and record:
            grants = current_access(request)
            actor = grants["user_id"]
            prior = previous_intent(actor, idempotency_key)
            if prior and prior["path"] == source_path + "/record" and prior["params"] == key:
                authorization = prior["authorization"]
            else:
                current = request.app.state.source.request(
                    "GET", source_path + "/record", actor=actor, params=key
                )
                authorization = {"merchant_id": current["data"]["merchant_id"]}
            # A deleted shop's receipt is replayable only while its merchant grant remains current.
            writable(resource, grants, authorization)
        else:
            actor = identity(request, key if record else body)
        intent = {
            "method": method,
            "path": source_path + ("/record" if record else ""),
            "params": key,
            "body": body,
        }
        if authorization is not None:
            intent["authorization"] = authorization
        run = accept(actor, idempotency_key, "mutation", intent)
        result = resolve_mutation(run["run_id"], request.app.state.source)
        request.app.state.worker.wake()
        return result

    def create(request: Request, body: model) -> dict:
        if request.query_params:
            raise APIError(422, "INVALID_FILTER")
        return write(request, "POST", body.model_dump(mode="json"))

    def patch(request: Request, body: patch_model) -> dict:
        return write(request, "PATCH", body.model_dump(mode="json", exclude_unset=True), True)

    def remove(request: Request) -> dict:
        return write(request, "DELETE", record=True)

    key_parameters = [
        {"name": k, "in": "query", "required": True, "schema": v}
        for k, v in key_model.model_json_schema()["properties"].items()
    ]
    extra = {"parameters": key_parameters}
    app.add_api_route(path, listing, methods=["GET"], response_model=SourcePage[model])
    app.add_api_route(
        path, create, methods=["POST"], response_model=Mutation[model], status_code=202
    )
    app.add_api_route(
        path + "/record",
        get_record,
        methods=["GET"],
        response_model=SourceResult[model],
        openapi_extra=extra,
    )
    app.add_api_route(
        path + "/record",
        patch,
        methods=["PATCH"],
        response_model=Mutation[model],
        status_code=202,
        openapi_extra=extra,
    )
    app.add_api_route(
        path + "/record",
        remove,
        methods=["DELETE"],
        response_model=Mutation[dict],
        status_code=202,
        openapi_extra=extra,
    )


def register(app: FastAPI) -> None:
    for resource in RESOURCES.values():
        register_resource(app, resource)
