"""Phone-only identification. Knowledge of a phone number is sufficient for access."""

import re
from contextvars import ContextVar

from pydantic import BaseModel
from starlette.responses import JSONResponse

from app.settings import Settings


class Principal(BaseModel):
    subject: str
    shop: str
    scopes: set[str]


class Identity(BaseModel):
    subject: str
    shops: set[str]
    scopes: set[str]

    def select_shop(self, shop_key: str | None = None) -> Principal:
        if shop_key is None and len(self.shops) == 1:
            shop_key = next(iter(self.shops))
        if shop_key not in self.shops:
            raise ValueError("Choose an authorized shop_key from list_shops")
        return Principal(subject=self.subject, shop=shop_key, scopes=self.scopes)


principal: ContextVar[Identity] = ContextVar("principal")


class Authentication:
    def __init__(self, app, settings: Settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["path"] == "/health":
            await self.app(scope, receive, send)
            return
        try:
            phones = [v for k, v in scope["headers"] if k.lower() == b"x-phone-number"]
            if len(phones) != 1:
                raise ValueError()
            phone = phones[0].decode("ascii")
            if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
                raise ValueError()
        except ValueError:
            await JSONResponse({"error": "Unauthorized"}, status_code=401)(scope, receive, send)
            return
        from app.database import Database

        try:
            shops = await Database(self.settings).authorized_shops(phone)
        except Exception:
            await JSONResponse({"error": "Access lookup unavailable"}, status_code=503)(
                scope, receive, send
            )
            return
        shops &= self.settings.shops.keys()
        if not shops:
            await JSONResponse({"error": "Unauthorized"}, status_code=401)(scope, receive, send)
            return
        who = Identity(subject=phone, shops=shops, scopes=self.settings.scopes)
        context = principal.set(who)
        try:
            await self.app(scope, receive, send)
        finally:
            principal.reset(context)
