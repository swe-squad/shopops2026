"""Read-only fixture Data MCP and shared stateless Streamable HTTP endpoint."""

import json
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.contracts.errors import CoreError
from app.contracts.models import Conversation, Source
from app.contracts.repository import Repository
from app.contracts.tools import ToolResult
from app.tools.credentials import CredentialError, Credentials, VerifiedCredential, same_identity
from app.tools.validation import PERMISSIONS, definitions, validate_arguments, validate_result

SERVICE_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_VERSION = "2025-06-18"
Handler = Callable[[Conversation, str, dict], Awaitable[ToolResult]]


def build_mcp_app(
    *,
    repository: Repository,
    credentials: Credentials,
    audience: str,
    names: frozenset[str],
    handler: Handler,
    allowed_origins: frozenset[str] = frozenset(),
) -> FastAPI:
    """Mount at the configured MCP path; this subapp's endpoint is `/`."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, redirect_slashes=False)

    async def identity(request: Request) -> VerifiedCredential:
        origin = request.headers.get("origin")
        if origin is not None and origin not in allowed_origins:
            raise CredentialError()
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            raise CredentialError()
        return credentials.verify(auth[7:], audience)

    @app.get("/")
    async def get_endpoint(request: Request) -> Response:
        try:
            await identity(request)
        except CredentialError:
            return Response(status_code=401)
        return Response(status_code=405, headers={"Allow": "POST"})

    @app.post("/")
    async def post_endpoint(request: Request) -> Response:
        # Authenticate every HTTP message before JSON decoding or repository access.
        if request.headers.get("origin") not in (None, *allowed_origins):
            return Response(status_code=403)
        try:
            credential = await identity(request)
        except CredentialError:
            return Response(status_code=401)
        accept = request.headers.get("accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            return Response(status_code=406)
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return Response(status_code=415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                return Response(status_code=413)
        try:
            message = json.loads(body)
        except ValueError:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "invalid_input"},
                },
                status_code=400,
            )
        if (
            not isinstance(message, dict)
            or message.get("jsonrpc") != "2.0"
            or not isinstance(message.get("method"), str)
        ):
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "invalid_input"},
                },
                status_code=400,
            )
        rpc_id = message.get("id")
        method = message["method"]
        params = message.get("params", {})

        def rpc_error(code: int, error: str) -> JSONResponse:
            return JSONResponse(
                {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": error}}
            )

        def rpc_result(value: dict) -> JSONResponse:
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": value})

        def tool_result(result: ToolResult) -> JSONResponse:
            value = result.model_dump(mode="json")
            return rpc_result(
                {
                    "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                    "structuredContent": value,
                    "isError": result.error is not None,
                }
            )

        if (
            method != "initialize"
            and request.headers.get("mcp-protocol-version") != PROTOCOL_VERSION
        ):
            return Response(status_code=400)
        if not isinstance(params, dict):
            return rpc_error(-32602, "invalid_input")
        try:
            conversation = await repository.get_conversation(
                credential.scope, credential.conversation_id
            )
            if (
                not same_identity(conversation.scope, credential.scope)
                or conversation.config.revision != credential.config_revision
            ):
                raise CredentialError()
        except CoreError, CredentialError:
            if method == "tools/call":
                return tool_result(ToolResult(error="permission_denied"))
            return rpc_error(-32001, "permission_denied")
        if method == "initialize":
            if not isinstance(params.get("protocolVersion"), str):
                return rpc_error(-32602, "invalid_input")
            return rpc_result(
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": audience, "version": "1"},
                }
            )
        if method == "notifications/initialized" and "id" not in message:
            return Response(status_code=202)
        if "id" not in message:
            return Response(status_code=202)
        if method == "ping":
            return rpc_result({})
        if method == "tools/list":
            available = [
                d
                for d in definitions()
                if d.name in names
                and d.name in conversation.config.capabilities
                and PERMISSIONS[d.name] in credential.permissions
            ]
            return rpc_result(
                {
                    "tools": [
                        dict(name=d.name, description=d.description, inputSchema=d.input_schema)
                        for d in available
                    ]
                }
            )
        if method != "tools/call":
            return rpc_error(-32601, "invalid_input")
        name = params.get("name")
        if not isinstance(name, str) or name not in names or set(params) - {"name", "arguments"}:
            return tool_result(ToolResult(error="invalid_input"))
        if (
            name not in conversation.config.capabilities
            or PERMISSIONS[name] not in credential.permissions
        ):
            return tool_result(ToolResult(error="permission_denied"))
        try:
            arguments = validate_arguments(name, params.get("arguments", {}))
        except ValueError, TypeError:
            return tool_result(ToolResult(error="invalid_input"))
        try:
            result = await handler(conversation, name, arguments)
            return tool_result(validate_result(name, result.model_dump(mode="json")))
        except CoreError as exc:
            error = "permission_denied" if exc.code == "permission_denied" else "not_found"
            return tool_result(ToolResult(error=error))
        except ValueError, TypeError, KeyError:
            return tool_result(ToolResult(error="upstream_unavailable"))

    return app


def build_data_app(
    *,
    repository: Repository,
    credentials: Credentials,
    mode: str = "mock",
    fixture_path: Path | None = None,
    allowed_origins: frozenset[str] = frozenset(),
) -> FastAPI | None:
    if mode == "remote":
        return None
    if mode != "mock":
        raise ValueError("DATA_MCP_MODE must be mock or remote")
    fixture = json.loads(
        (fixture_path or SERVICE_ROOT / "fixtures/business/returns-v1.json").read_text()
    )
    shops = {(s["tenant_id"], s["shop_id"]): s for s in fixture["shops"]}

    async def execute(conversation: Conversation, name: str, arguments: dict) -> ToolResult:
        scope = conversation.scope
        shop = shops.get((scope.tenant_id, scope.shop_id))
        if shop is None:
            return ToolResult(error="not_found")
        product = shop["products"].get(arguments["sku"])
        if product is None:
            return ToolResult(error="not_found")
        start, end = (
            date.fromisoformat(arguments["start_date"]),
            date.fromisoformat(arguments["end_date"]),
        )
        reference = (
            f"fixture:{fixture['id']}:{scope.tenant_id}:{scope.shop_id}:"
            f"{arguments['sku']}:{start}:{end}:{name}"
        )
        sources = (Source(type="data", reference=reference),)
        if name == "get_review_summary":
            reviews = [r for r in product["reviews"] if str(start) <= r["date"] <= str(end)]
            categories = {}
            for review in reviews:
                category = categories.setdefault(
                    review["category"], {"category": review["category"], "count": 0, "evidence": []}
                )
                category["count"] += review["count"]
                category["evidence"].append(f"fixture:{fixture['id']}:{review['id']}")
            data = dict(arguments, categories=list(categories.values()))
        else:

            def counts(a: date, b: date) -> dict:
                rows = [r for r in product["daily"] if str(a) <= r["date"] <= str(b)]
                orders = sum(r["orders"] for r in rows)
                returns = sum(r["returns"] for r in rows)
                return dict(
                    start_date=str(a),
                    end_date=str(b),
                    orders=orders,
                    returns=returns,
                    return_rate=round(returns / orders * 100, 6) if orders else None,
                )

            current = counts(start, end)
            baseline = counts(
                start - timedelta(days=(end - start).days + 1), start - timedelta(days=1)
            )
            change = (
                round(current["return_rate"] - baseline["return_rate"], 6)
                if current["return_rate"] is not None and baseline["return_rate"] is not None
                else None
            )
            data = dict(
                current,
                sku=arguments["sku"],
                timezone=fixture["timezone"],
                baseline=baseline,
                change_percentage_points=change,
            )
        return ToolResult(data=data, sources=sources, observed_at=fixture["observed_at"])

    return build_mcp_app(
        repository=repository,
        credentials=credentials,
        audience="agent-core:data",
        names=frozenset({"get_return_metrics", "get_review_summary"}),
        handler=execute,
        allowed_origins=allowed_origins,
    )
