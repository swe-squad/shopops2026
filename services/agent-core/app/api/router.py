from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException

from app.auth.dependencies import Unauthorized
from app.contracts.errors import CoreError, InvalidCursor
from app.contracts.identity import AuthContext
from app.contracts.repository import Repository

STATUS = {
    "unauthorized": 401,
    "permission_denied": 403,
    "not_found": 404,
    "configuration_conflict": 409,
    "idempotency_conflict": 409,
    "conversation_busy": 409,
    "invalid_cursor": 422,
    "invalid_input": 422,
}


def error_response(code: str, status: int, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": "Không thể xử lý yêu cầu.",
                "retryable": status == 503,
            },
            "request_id": request_id,
        },
        headers={"WWW-Authenticate": "Bearer"} if status == 401 else {},
    )


class SafeRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request: Request):
            request_id = str(uuid4())
            try:
                # Stream and bound before FastAPI parses JSON, including chunked requests.
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 65536:
                        return error_response("body_too_large", 413, request_id)
                request._body = bytes(body)
                return await original(request)
            except CoreError as exc:
                return error_response(exc.code, STATUS.get(exc.code, 500), request_id)
            except HTTPException as exc:
                status = 422 if exc.status_code == 400 else exc.status_code
                code = "invalid_input" if status == 422 else "internal_error"
                return error_response(code, status, request_id)
            except RequestValidationError:
                return error_response("invalid_input", 422, request_id)
            except Exception:
                return error_response("internal_error", 500, request_id)

        return handle


def validate_cursor(after: str | None) -> str | None:
    if after is not None:
        try:
            UUID(after)
        except ValueError:
            raise InvalidCursor() from None
    return after


def build_api_router(
    repository: Repository,
    authenticate: Callable[[str], Awaitable[AuthContext]],
    readiness: Callable[[], Awaitable[bool]],
) -> APIRouter:
    from app.api.conversations import add_conversations
    from app.api.health import add_health
    from app.api.orchestrators import add_orchestrators
    from app.api.runs import add_runs

    router = APIRouter(prefix="/api/v1", route_class=SafeRoute)

    async def identity(request: Request) -> AuthContext:
        parts = request.headers.get("authorization", "").split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise Unauthorized()
        return await authenticate(parts[1])

    add_orchestrators(router, repository, identity)
    add_conversations(router, repository, identity)
    add_runs(router, repository, identity)
    add_health(router, readiness)
    return router
