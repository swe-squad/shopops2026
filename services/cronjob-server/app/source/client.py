import re

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.api.common import APIError
from app.source.entities import Phone
from app.source.models import Snapshot


class Access(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: Phone
    merchant_ids: list[str]
    shop_keys: list[str]


class SourceClient:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None) -> None:
        self.base_url, self.transport = base_url, transport

    def request(
        self,
        method: str,
        path: str,
        *,
        actor: str | None = None,
        key: str | None = None,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        headers = {}
        if actor is not None:
            headers["X-Demo-User-Id"] = actor
        if key is not None:
            headers["Idempotency-Key"] = key
        try:
            with httpx.Client(
                base_url=self.base_url,
                transport=self.transport,
                timeout=httpx.Timeout(30, connect=5),
            ) as client:
                response = client.request(method, path, headers=headers, params=params, json=body)
        except httpx.RequestError:
            raise APIError(503, "SOURCE_UNAVAILABLE") from None
        if response.status_code >= 500:
            raise APIError(503, "SOURCE_UNAVAILABLE")
        try:
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError()
        except ValueError:
            raise APIError(422, "INVALID_SOURCE_RESPONSE") from None
        if response.is_error:
            error = payload.get("error")
            code = error.get("code", "") if isinstance(error, dict) else ""
            if not isinstance(code, str) or not re.fullmatch(r"[A-Z_]{1,80}", code):
                code = "SOURCE_REQUEST_REJECTED"
            raise APIError(response.status_code, code)
        return payload

    def access(self, user_id: str) -> dict:
        payload = self.request("GET", "/v1/access", params={"user_id": user_id})
        try:
            result = Access.model_validate(payload)
            if result.user_id != user_id:
                raise ValueError()
        except ValidationError, ValueError:
            raise APIError(422, "INVALID_SOURCE_RESPONSE") from None
        return result.model_dump()

    def snapshot(self) -> dict:
        try:
            return Snapshot.model_validate(self.request("GET", "/v1/snapshot")).model_dump(
                mode="json"
            )
        except ValidationError:
            raise APIError(422, "INVALID_SNAPSHOT") from None
