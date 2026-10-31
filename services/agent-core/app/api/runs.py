from fastapi import APIRouter, Depends, Query

from app.api.conversations import find_scoped
from app.api.router import STATUS, validate_cursor
from app.api.schemas import EventOutput, EventsOutput, RunOutput
from app.auth.dependencies import require_permission
from app.contracts.identity import AuthContext
from app.contracts.repository import Repository

SAFE_ERRORS = frozenset(STATUS) | {
    "timeout",
    "upstream_unavailable",
    "invalid_output",
    "provider_outcome_unknown",
    "tool_limit_exceeded",
    "cancelled",
}
SAFE_EVENTS = {
    "queued",
    "running",
    "waiting_tool",
    "reconciling",
    "completed",
    "failed",
    "cancelled",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "status",
}
SAFE_TOOLS = {
    "get_review_summary",
    "get_return_metrics",
    "search_knowledge",
    "get_conversation_history",
}


def public_error(value: str | None) -> str | None:
    return value if value is None or value in SAFE_ERRORS else "internal_error"


def add_runs(router: APIRouter, repository: Repository, identity) -> None:
    auth_dependency = Depends(identity)

    @router.get("/runs/{run_id}", response_model=RunOutput)
    async def get_run(run_id: str, auth: AuthContext = auth_dependency):
        _, run = await find_scoped(repository, auth, run_id, run=True)
        require_permission(auth, "history:read")
        return RunOutput(
            run_id=run.id, status=run.state, response=run.response, error=public_error(run.error)
        )

    @router.get("/runs/{run_id}/events", response_model=EventsOutput)
    async def events(
        run_id: str,
        after: str | None = None,
        limit: int = Query(50, ge=1, le=100),
        auth: AuthContext = auth_dependency,
    ):
        scope, _ = await find_scoped(repository, auth, run_id, run=True)
        require_permission(auth, "history:read")
        page = await repository.get_events(scope, run_id, validate_cursor(after), limit)
        items = [
            EventOutput(
                id=e.id,
                run_id=e.run_id,
                sequence=e.sequence,
                type=e.type if e.type in SAFE_EVENTS else "status",
                tool_name=e.tool_name if e.tool_name in SAFE_TOOLS else None,
                error=public_error(e.error),
                created_at=e.created_at,
            )
            for e in page.items
        ]
        return EventsOutput(items=items, next_cursor=page.next_cursor)
