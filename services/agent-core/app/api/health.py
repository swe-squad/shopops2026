from collections.abc import Awaitable, Callable

from fastapi import APIRouter

from app.api.router import error_response
from app.api.schemas import HealthOutput


def add_health(router: APIRouter, readiness: Callable[[], Awaitable[bool]]) -> None:
    @router.get("/health", response_model=HealthOutput)
    async def health():
        return HealthOutput(status="ok")

    @router.get("/ready", response_model=HealthOutput)
    async def ready():
        try:
            available = await readiness()
        except Exception:
            available = False
        if not available:
            from uuid import uuid4

            return error_response("not_ready", 503, str(uuid4()))
        return HealthOutput(status="ok")
