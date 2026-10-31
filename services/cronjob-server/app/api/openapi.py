"""Document required headers and composite keys consumed by the generated routes."""

from fastapi.openapi.utils import get_openapi

from app.source.entities import RESOURCES


def install_openapi(app) -> None:
    def schema() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        value = get_openapi(title=app.title, version=app.version, routes=app.routes)
        for path, operations in value["paths"].items():
            if not path.startswith("/v1/"):
                continue
            for method, operation in operations.items():
                parameters = operation.setdefault("parameters", [])
                names = {(p["in"], p["name"]) for p in parameters}

                def add(
                    name: str,
                    location: str,
                    required: bool,
                    field: dict,
                    *,
                    names: set = names,
                    parameters: list = parameters,
                ) -> None:
                    if (location, name) not in names:
                        parameters.append(
                            {"name": name, "in": location, "required": required, "schema": field}
                        )
                        names.add((location, name))

                if not path.startswith("/v1/admin/") and path not in {"/v1/snapshot", "/v1/access"}:
                    add(
                        "X-Demo-User-Id",
                        "header",
                        True,
                        {"type": "string", "pattern": r"^\+[1-9][0-9]{7,14}$"},
                    )
                if method in {"post", "patch", "delete"}:
                    add(
                        "Idempotency-Key",
                        "header",
                        True,
                        {"type": "string", "minLength": 1, "maxLength": 200},
                    )
                name = path.split("/")[-2] if path.endswith("/record") else path.split("/")[-1]
                resource = RESOURCES.get(name)
                if resource and path.endswith("/record"):
                    fields = resource.model.model_json_schema()["properties"]
                    for key in resource.keys:
                        add(key, "query", True, fields[key])
                elif method == "get" and resource:
                    add(
                        "limit",
                        "query",
                        False,
                        {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                    )
                    add("offset", "query", False, {"type": "integer", "minimum": 0, "default": 0})
                    if "shop_key" in resource.model.model_fields:
                        add("shop_key", "query", False, {"type": "string"})
                for status in ("403", "404", "409", "422", "503"):
                    operation.setdefault("responses", {})[status] = {
                        "description": "Sanitized error",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["error"],
                                    "properties": {
                                        "error": {
                                            "type": "object",
                                            "required": ["code", "message"],
                                            "properties": {
                                                "code": {"type": "string"},
                                                "message": {"type": "string"},
                                            },
                                        }
                                    },
                                }
                            }
                        },
                    }
        app.openapi_schema = value
        return value

    app.openapi = schema
