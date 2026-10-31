"""Authenticated MCP bridge to the full-snapshot pipeline; no time-range backfill claim."""

import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Query, Request
from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.api.common import APIError
from app.pipeline.publish import digest
from app.storage.db import connect

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]


class Refresh(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=256)
    shop_key: str = Field(min_length=1, max_length=256)
    resource: Literal["snapshot"]
    start: AwareDatetime
    end: AwareDatetime
    idempotency_key: Identifier

    @model_validator(mode="after")
    def window(self) -> Refresh:
        if self.start >= self.end:
            raise ValueError("Use a nonempty [start,end) window")
        self.start = self.start.astimezone(UTC)
        self.end = self.end.astimezone(UTC)
        return self


class Accepted(BaseModel):
    operation_id: UUID
    status: Literal["queued", "processing", "snapshot_ready", "failed"]


class Operation(Accepted):
    subject: str
    shop_key: str
    coverage: None = None
    refresh_mode: Literal["full_snapshot"] = "full_snapshot"
    applied_source_revision: int | None = None
    error_code: Literal["SYNCHRONIZATION_FAILED"] | None = None


def authorize(request: Request, subject: str, shop_key: str) -> None:
    token = os.getenv("MCP_SERVICE_TOKEN", "")
    supplied = request.headers.get("Authorization", "")
    if not token or not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
        raise APIError(401, "SERVICE_AUTH_REQUIRED")
    try:
        users = json.loads(os.getenv("MCP_SUBJECT_USERS_JSON", "{}"))
        user = users.get(subject)
        if not isinstance(user, str) or not user:
            raise ValueError()
    except ValueError, AttributeError:
        raise APIError(403, "ACCESS_DENIED") from None
    grants = request.app.state.source.access(user)
    if shop_key not in grants["shop_keys"]:
        raise APIError(404, "NOT_FOUND")
    # Intersect current source ownership with the published shop, as the read API does.
    with connect() as conn:
        if not conn.execute(
            "SELECT 1 FROM core.shops WHERE shop_key=%s AND merchant_id=ANY(%s)",
            (shop_key, grants["merchant_ids"]),
        ).fetchone():
            raise APIError(404, "NOT_FOUND")


def status(value: str) -> str:
    mapping = {
        "queued": "queued",
        "running": "processing",
        "succeeded": "snapshot_ready",
        "failed": "failed",
    }
    if value not in mapping:
        raise APIError(503, "INVALID_RUN_STATE")
    return mapping[value]


def register(app: FastAPI) -> None:
    @app.post("/v1/refreshes", status_code=202, response_model=Accepted)
    def refresh(request: Request, body: Refresh) -> dict:
        authorize(request, body.subject, body.shop_key)
        if request.query_params:
            raise APIError(422, "INVALID_FILTER")
        payload = body.model_dump(mode="json")
        with connect() as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,8173606))", (body.shop_key,)
            )
            previous = conn.execute(
                "SELECT f.request,r.run_id,r.status FROM sync.mcp_refreshes f "
                "JOIN sync.runs r USING(run_id) "
                "WHERE f.subject=%s AND f.shop_key=%s AND f.idempotency_key=%s",
                (body.subject, body.shop_key, body.idempotency_key),
            ).fetchone()
            if previous:
                if previous["request"] != payload:
                    raise APIError(409, "IDEMPOTENCY_CONFLICT")
                return {"operation_id": previous["run_id"], "status": status(previous["status"])}
            now = datetime.now(UTC)
            if body.start < now - timedelta(days=365) or body.end > now:
                raise APIError(422, "REFRESH_OUTSIDE_LOOKBACK")
            if conn.execute(
                "SELECT 1 FROM sync.mcp_refreshes WHERE shop_key=%s "
                "AND created_at > now()-interval '300 seconds'",
                (body.shop_key,),
            ).fetchone():
                raise APIError(429, "REFRESH_COOLDOWN")
            # Serialize the global queue budget across different shops.
            conn.execute("SELECT pg_advisory_xact_lock(8173607)")
            queued = conn.execute(
                "SELECT count(*) n FROM sync.runs WHERE status IN ('queued','running')"
            ).fetchone()["n"]
            if queued >= 100:
                raise APIError(429, "REFRESH_QUEUE_FULL")
            operation = uuid4()
            conn.execute(
                "INSERT INTO sync.runs(run_id,actor,idempotency_key,intent_hash,trigger,status) "
                "VALUES (%s,%s,%s,%s,'manual','queued')",
                (operation, "mcp:" + body.subject, str(operation), digest(payload)),
            )
            conn.execute(
                "INSERT INTO sync.mcp_refreshes(subject,shop_key,idempotency_key,request,run_id) "
                "VALUES (%s,%s,%s,%s,%s)",
                (body.subject, body.shop_key, body.idempotency_key, Jsonb(payload), operation),
            )
        request.app.state.worker.wake()
        return {"operation_id": operation, "status": "queued"}

    @app.get("/v1/operations/{operation_id}", response_model=Operation)
    def operation(
        request: Request,
        operation_id: UUID,
        subject: Annotated[str, Query(min_length=1, max_length=256)],
        shop_key: Annotated[str, Query(min_length=1, max_length=256)],
    ) -> dict:
        authorize(request, subject, shop_key)
        if set(request.query_params) != {"subject", "shop_key"}:
            raise APIError(422, "INVALID_FILTER")
        with connect() as conn:
            row = conn.execute(
                "SELECT r.status,r.applied_revision FROM sync.mcp_refreshes f "
                "JOIN sync.runs r USING(run_id) "
                "WHERE f.run_id=%s AND f.subject=%s AND f.shop_key=%s",
                (operation_id, subject, shop_key),
            ).fetchone()
        if not row:
            raise APIError(404, "NOT_FOUND")
        return {
            "operation_id": operation_id,
            "subject": subject,
            "shop_key": shop_key,
            "status": status(row["status"]),
            "applied_source_revision": row["applied_revision"],
            "error_code": "SYNCHRONIZATION_FAILED" if row["status"] == "failed" else None,
        }
