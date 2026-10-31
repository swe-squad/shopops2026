"""Bounded HTTP-only application boundary. No provider SDK or upstream redirect handling."""

import asyncio
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.contracts import Source


class CoreError(Exception):
    pass


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise CoreError("Invalid application identifier")
    return value


def cursor(value: str) -> str:
    try:
        return str(UUID(value))
    except ValueError, TypeError, AttributeError:
        raise CoreError("Invalid history cursor") from None


class CoreAPI:
    def __init__(self, url: str, transport=None) -> None:
        self.client = httpx.AsyncClient(
            base_url=url.rstrip("/") + "/api/v1/",
            timeout=10,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    async def request(self, method: str, path: str, token: str, body=None) -> dict:
        async with self.client.stream(
            method, path, headers={"Authorization": f"Bearer {token}"}, json=body
        ) as response:
            if response.status_code not in {200, 201, 202}:
                if response.status_code in {403, 404, 409, 410, 422}:
                    raise HTTPException(
                        response.status_code, "Core request could not be completed."
                    )
                raise CoreError("Core unavailable")
            data = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=65536):
                data.extend(chunk)
                if len(data) > 4 * 1048576:
                    raise CoreError("Core response too large")
            import json

            result = json.loads(data)
            if not isinstance(result, dict):
                raise CoreError("Invalid Core response")
            route = path.split("?")[0]
            if route.endswith("/history"):
                CoreHistory.model_validate(result)
            elif route.startswith("runs/") and not route.endswith("/artifacts"):
                CoreRun.model_validate(result)
            if route.endswith("/messages") and response.status_code != 202:
                raise CoreError("Missing accepted receipt")
            return result

    async def pages(self, path: str, token: str) -> list[dict]:
        seen, items, after = set(), [], None
        async with asyncio.timeout(30):
            for _ in range(100):
                page = await self.request("GET", path + (f"&after={after}" if after else ""), token)
                if not isinstance(page.get("items"), list):
                    raise CoreError("Invalid Core page")
                items.extend(page["items"])
                after = page.get("next_cursor")
                if after is None:
                    return items
                after = cursor(after)
                if after in seen:
                    raise CoreError("Repeated Core cursor")
                seen.add(after)
        raise CoreError("Core pagination limit")

    async def content(self, artifact: dict, token: str) -> bytes:
        async with self.client.stream(
            "GET",
            f"artifacts/{identifier(artifact['id'])}/content",
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            if response.status_code == 410:
                raise HTTPException(410, "Report is no longer available.")
            if response.status_code != 200:
                raise CoreError("Download unavailable")
            if response.headers.get("content-type", "").split(";")[0] != artifact["media_type"]:
                raise CoreError("Invalid artifact media")
            data = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=65536):
                data.extend(chunk)
                if len(data) > 1048576 or len(data) > artifact["size"]:
                    raise CoreError("Artifact too large")
            import hashlib

            if (
                len(data) != artifact["size"]
                or hashlib.sha256(data).hexdigest() != artifact["sha256"]
            ):
                raise CoreError("Invalid artifact content")
            return bytes(data)


# Public application responses only; provider/session identifiers never cross this boundary.
class CoreResponse(BaseModel):
    kind: Literal["answer", "clarification", "cannot_answer"]
    text: str = Field(min_length=1, max_length=32000)
    sources: list[Source] = Field(default_factory=list, max_length=100)


class CoreRun(BaseModel):
    run_id: str
    status: Literal[
        "queued", "running", "waiting_tool", "reconciling", "completed", "failed", "cancelled"
    ]
    response: CoreResponse | None = None
    error: str | None = None


class CoreMessage(BaseModel):
    id: str
    conversation_id: str
    run_id: str
    role: Literal["user", "assistant"]
    content: str = Field(max_length=32000)
    sequence: int = Field(ge=1, strict=True)
    created_at: datetime


class CoreHistory(BaseModel):
    items: list[CoreMessage] = Field(max_length=100)
    next_cursor: str | None = None
