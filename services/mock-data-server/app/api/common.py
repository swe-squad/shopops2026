from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import IntegrityError, OperationalError


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        self.status, self.code = status, code
        self.message = message or code.replace("_", " ").capitalize()
        super().__init__(self.message)


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    def api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}}
        )

    @app.exception_handler(RequestValidationError)
    def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Invalid request"}},
        )

    @app.exception_handler(IntegrityError)
    def integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "REFERENCE_CONFLICT", "message": "Conflicting record"}},
        )

    @app.exception_handler(OperationalError)
    def database_error(request: Request, exc: OperationalError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "DATABASE_UNAVAILABLE", "message": "Database unavailable"}},
        )
