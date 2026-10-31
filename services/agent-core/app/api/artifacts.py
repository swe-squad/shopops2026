"""Scoped artifact delivery; resolve local ownership before any remote call."""

import asyncio
import hashlib
import re
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from app.api.conversations import find_scoped
from app.api.router import validate_cursor
from app.auth.dependencies import require_permission
from app.contracts.errors import ArtifactInvalid, ArtifactTransient, ArtifactUnavailable, NotFound
from app.contracts.identity import AuthContext
from app.contracts.provider import AgentProvider
from app.contracts.repository import Repository
from app.contracts.runtime import ArtifactRecord


def safe_filename(path: str, media_type: str) -> str:
    prefix = "/workspace/outputs/"
    if not path.startswith(prefix):
        raise ArtifactInvalid()
    name = path[len(prefix) :]
    suffix = ".json" if media_type == "application/json" else ".md"
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", name)
        or ".." in name
        or not name.endswith(suffix)
        or PurePosixPath(path).as_posix() != path
    ):
        raise ArtifactInvalid()
    return name


class ArtifactOutput(BaseModel):
    id: str
    run_id: str
    filename: str
    media_type: str
    size: int
    sha256: str
    availability: str


class ArtifactPage(BaseModel):
    items: list[ArtifactOutput]
    next_cursor: str | None = None


def public_record(record: ArtifactRecord) -> ArtifactOutput:
    return ArtifactOutput(
        id=record.id,
        run_id=record.run_id,
        filename=safe_filename(record.path, record.media_type),
        media_type=record.media_type,
        size=record.size,
        sha256=record.sha256,
        availability=record.availability,
    )


def add_artifacts(
    router: APIRouter, repository: Repository, identity, provider: AgentProvider | None
) -> None:
    dependency = Depends(identity)

    @router.get("/runs/{run_id}/artifacts", response_model=ArtifactPage)
    async def listing(
        run_id: str,
        after: str | None = None,
        limit: int = Query(50, ge=1, le=100),
        auth: AuthContext = dependency,
    ):
        require_permission(auth, "history:read")
        scope, _ = await find_scoped(repository, auth, run_id, run=True)
        page = await repository.list_artifacts(scope, run_id, validate_cursor(after), limit)
        return ArtifactPage(
            items=[public_record(a) for a in page.items], next_cursor=page.next_cursor
        )

    @router.get("/artifacts/{artifact_id}/content")
    async def content(artifact_id: str, auth: AuthContext = dependency):
        require_permission(auth, "history:read")
        record = None
        for shop in sorted(auth.shop_ids):
            try:
                record = await repository.get_artifact(auth.scope(shop), artifact_id)
                break
            except NotFound:
                continue
        if record is None:
            raise NotFound()
        filename = safe_filename(record.path, record.media_type)
        if record.availability != "available":
            raise ArtifactUnavailable()
        if provider is None:
            raise ArtifactTransient()
        try:
            async with asyncio.timeout(15):
                payload = await provider.read_artifact(
                    record.session_id, record.provider_id, max_bytes=record.size
                )
        except ArtifactUnavailable, ArtifactInvalid, ArtifactTransient:
            raise
        except Exception:
            raise ArtifactTransient() from None
        if (
            not isinstance(payload, bytes)
            or len(payload) != record.size
            or hashlib.sha256(payload).hexdigest() != record.sha256
        ):
            raise ArtifactInvalid()
        return Response(
            payload,
            media_type=record.media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )
