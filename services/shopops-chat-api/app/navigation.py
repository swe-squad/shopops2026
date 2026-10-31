import httpx
from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, field_validator


class Navigation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str

    @field_validator("url")
    @classmethod
    def valid(cls, value: str) -> str:
        from urllib.parse import unquote, urlsplit

        parsed = urlsplit(value)
        decoded = unquote(value)
        invalid = (
            not value
            or len(value) > 2000
            or "\\" in decoded
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in decoded)
        )
        if value.startswith("/"):
            invalid = (
                invalid
                or bool(parsed.netloc)
                or not (parsed.path == "/shop" or parsed.path.startswith("/shop/"))
                or ".." in decoded
            )
        else:
            invalid = (
                invalid
                or parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
            )
        try:
            _port = parsed.port
        except ValueError:
            invalid = True
        if invalid:
            raise ValueError("Invalid shop URL")
        return value


def add_navigation(app, config, authorized, transport):
    identity_dependency = Depends(authorized)

    @app.post("/api/chat/navigation")
    async def navigation(item: Navigation, who=identity_dependency):
        if not config.token:
            raise HTTPException(503, "Shop navigation is unavailable.")
        async with httpx.AsyncClient(
            timeout=10, follow_redirects=False, transport=transport
        ) as client:
            response = await client.post(
                config.shop_url.rstrip("/") + "/api/operations/navigation",
                headers={"Authorization": f"Bearer {config.token}"},
                json={"url": item.url},
            )
        if response.status_code not in {200, 201, 202, 204}:
            raise HTTPException(503, "Shop navigation is unavailable.")
        return Response(status_code=204)
