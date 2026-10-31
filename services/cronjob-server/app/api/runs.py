from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.api.auth import current_access, visible_shops
from app.api.common import APIError
from app.api.contracts import Empty, Pagination
from app.api.reads import pagination
from app.jobs.store import accept
from app.storage.db import connect


class Accepted(BaseModel):
    run_id: UUID
    sync_status: str
    status_url: str


class Run(BaseModel):
    run_id: UUID
    trigger: str
    status: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    attempts: int
    minimum_revision: int
    applied_revision: int | None
    mutation_status: str | None
    error_stage: str | None
    error_code: str | None
    shop_counts: dict[str, dict[str, int]]


class RunPage(BaseModel):
    data: list[Run]
    pagination: Pagination


def present(conn, row: dict, grants: dict | None) -> dict:
    result = dict(row)
    counts = (row["result"] or {}).get("shop_counts", {})
    if grants is not None:
        allowed = visible_shops(conn, grants)
        counts = {k: v for k, v in counts.items() if k in allowed}
        if row["error_code"] and row["error_stage"] == "synchronization":
            result["error_code"] = "SYNCHRONIZATION_FAILED"
    result["shop_counts"] = counts
    mutation = conn.execute(
        "SELECT status FROM sync.mutation_intents WHERE run_id=%s", (row["run_id"],)
    ).fetchone()
    result["mutation_status"] = mutation["status"] if mutation else None
    return Run.model_validate(result).model_dump()


def register_inspection(app: FastAPI, admin: bool) -> None:
    prefix = "/v1/admin/sync-runs" if admin else "/v1/sync-runs"

    def listing(request: Request) -> dict:
        grants = None if admin else current_access(request)
        limit, offset = pagination(request)
        if set(request.query_params) - {"limit", "offset"}:
            raise APIError(422, "INVALID_FILTER")
        with connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            rows = conn.execute(
                "SELECT * FROM sync.runs WHERE (%s OR actor=%s) ORDER BY created_at,run_id",
                (admin, "" if admin else grants["user_id"]),
            ).fetchall()
            data = [present(conn, r, grants) for r in rows[offset : offset + limit]]
        return {"data": data, "pagination": {"limit": limit, "offset": offset, "total": len(rows)}}

    def single(request: Request, run_id: UUID) -> dict:
        grants = None if admin else current_access(request)
        with connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            row = conn.execute(
                "SELECT * FROM sync.runs WHERE run_id=%s AND (%s OR actor=%s)",
                (run_id, admin, "" if admin else grants["user_id"]),
            ).fetchone()
            if not row:
                raise APIError(404, "NOT_FOUND")
            return present(conn, row, grants)

    app.add_api_route(prefix, listing, methods=["GET"], response_model=RunPage)
    app.add_api_route(prefix + "/{run_id}", single, methods=["GET"], response_model=Run)


def register(app: FastAPI) -> None:
    @app.post("/v1/sync-runs", status_code=202, response_model=Accepted)
    def trigger(request: Request, body: Empty) -> dict:
        grants = current_access(request)
        if request.query_params:
            raise APIError(422, "INVALID_FILTER")
        row = accept(grants["user_id"], request.headers.get("Idempotency-Key", ""), "manual", {})
        request.app.state.worker.wake()
        return {
            "run_id": row["run_id"],
            "sync_status": row["status"],
            "status_url": f"/v1/sync-runs/{row['run_id']}",
        }

    register_inspection(app, False)
    register_inspection(app, True)
