from collections.abc import Callable
from unicodedata import category
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator


class NavigationInput(BaseModel):
    url: str = Field(min_length=1, max_length=2000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if "\\" in value or any(
            character.isspace() or category(character) == "Cc" for character in value
        ):
            raise ValueError("URL must not contain whitespace, controls or backslashes")
        try:
            parsed = urlsplit(value)
            if value.startswith("/"):
                if parsed.netloc or not (
                    parsed.path == "/shop" or parsed.path.startswith("/shop/")
                ):
                    raise ValueError("Relative URLs must start with /shop/")
            elif (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            ):
                raise ValueError("URL must use absolute HTTP(S) without credentials")
            _port = parsed.port  # Validate malformed or out-of-range ports without a request.
        except ValueError as error:
            raise ValueError("Invalid navigation URL") from error
        return value


class Navigation(NavigationInput):
    id: int


def router(connect: Callable, authorize: Callable) -> APIRouter:
    api = APIRouter(prefix="/api/operations/navigation", dependencies=[Depends(authorize)])

    @api.get("", response_model=Navigation | None)
    def latest() -> dict | None:
        with connect() as db:
            row = db.execute("SELECT id,url FROM navigation ORDER BY id DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    @api.post("", response_model=Navigation, status_code=201)
    def navigate(item: NavigationInput) -> dict:
        with connect() as db:
            cursor = db.execute("INSERT INTO navigation(url) VALUES(?)", (item.url,))
            db.execute("DELETE FROM navigation WHERE id != ?", (cursor.lastrowid,))
            return {"id": cursor.lastrowid, "url": item.url}

    return api
