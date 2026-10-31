import os
import re
from dataclasses import dataclass
from typing import Self
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from app.catalog_source_models import RESOURCE_KEYS, RESOURCE_MODELS, SourcePage

SOURCE_RESPONSE_ERRORS = (httpx.HTTPError, ValueError)


class SourceUnavailable(Exception):
    """An upstream error whose contents must never reach the browser."""


class SourceNotFound(Exception):
    pass


class RevisionChanged(SourceUnavailable):
    pass


@dataclass(frozen=True)
class CatalogConfig:
    base_url: str
    user_id: str

    @classmethod
    def from_environment(cls) -> Self | None:
        mode = os.environ.get("SHOP_CATALOG_MODE", "disabled")
        if mode == "disabled":
            return None
        if mode != "source":
            raise RuntimeError("SHOP_CATALOG_MODE must be disabled or source")
        base_url = os.environ.get("CRONJOB_SERVER_URL", "")
        try:
            parsed = urlsplit(base_url)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
                and not any(character.isspace() for character in base_url)
                and "\\" not in base_url
            )
            _port = parsed.port
        except ValueError:
            valid = False
        if not valid:
            raise RuntimeError("CRONJOB_SERVER_URL must be an HTTP(S) origin without credentials")
        user_id = os.environ.get("SHOP_DATA_USER_ID", "")
        if not re.fullmatch(r"\+[1-9][0-9]{7,14}", user_id):
            raise RuntimeError("SHOP_DATA_USER_ID must be a configured E.164 source identity")
        return cls(base_url, user_id)


class SourceReader:
    """One response attempt: complete pages and one shared source revision."""

    def __init__(self, client: httpx.Client, user_id: str) -> None:
        self.client = client
        self.user_id = user_id
        self.revision: int | None = None

    def list(self, resource: str, shop_key: str | None = None) -> list[BaseModel]:
        model = RESOURCE_MODELS[resource]
        offset, total = 0, None
        rows: list[BaseModel] = []
        seen: set[tuple] = set()
        while True:
            params: dict[str, int | str] = {"limit": 200, "offset": offset}
            if shop_key is not None:
                params["shop_key"] = shop_key
            try:
                response = self.client.get(
                    f"/v1/mock/{resource}",
                    headers={"X-Demo-User-Id": self.user_id},
                    params=params,
                )
                if response.status_code in {403, 404}:
                    raise SourceNotFound()
                if response.status_code != 200:
                    raise SourceUnavailable()
                page = SourcePage.model_validate(response.json())
                values = [model.model_validate(row) for row in page.data]
            except SOURCE_RESPONSE_ERRORS:
                raise SourceUnavailable() from None
            if self.revision is not None and self.revision != page.source_revision:
                raise RevisionChanged()
            self.revision = page.source_revision
            pagination = page.pagination
            if (
                pagination.limit != 200
                or pagination.offset != offset
                or (total is not None and pagination.total != total)
            ):
                raise SourceUnavailable()
            total = pagination.total
            if len(values) != min(200, max(0, total - offset)):
                raise SourceUnavailable()
            for row in values:
                key = tuple(getattr(row, field) for field in RESOURCE_KEYS[resource])
                if key in seen or (shop_key is not None and row.shop_key != shop_key):
                    raise SourceUnavailable()
                seen.add(key)
                rows.append(row)
            offset += len(values)
            if offset >= total:
                return rows
