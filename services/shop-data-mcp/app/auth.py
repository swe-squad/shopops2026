"""JWT verification; agent-supplied tool arguments never define identity."""

import asyncio
from contextvars import ContextVar

import jwt
from pydantic import BaseModel

from app.settings import Settings


class Principal(BaseModel):
    subject: str
    shop: str
    scopes: set[str]


principal: ContextVar[Principal] = ContextVar("principal")


class Authentication:
    def __init__(self, app, settings: Settings):
        self.app, self.settings = app, settings
        self.keys = jwt.PyJWKClient(settings.jwks_url, timeout=5)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope["path"] in {
            "/health",
            "/.well-known/oauth-protected-resource/mcp",
        }:
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        try:
            token = headers.get(b"authorization", b"").decode()
            if not token.startswith("Bearer "):
                raise ValueError()
            token = token[7:]
            key = await asyncio.to_thread(self.keys.get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self.settings.audience,
                issuer=self.settings.issuer,
                options={"require": ["exp", "iat", "sub", "shop_key", "scope", "jti"]},
            )
            who = Principal(
                subject=claims["sub"], shop=claims["shop_key"], scopes=set(claims["scope"].split())
            )
            if who.shop not in self.settings.shops or "data:read" not in who.scopes:
                raise ValueError()
            if claims["exp"] - claims["iat"] > 3600:
                raise ValueError()
            from app.database import Database

            async with await Database(self.settings).connect() as conn:
                cursor = await conn.execute(
                    "SELECT 1 FROM mcp_control.revoked_tokens WHERE jti=%s", (claims["jti"],)
                )
                if await cursor.fetchone():
                    raise ValueError()
        except Exception:
            from starlette.responses import JSONResponse

            await JSONResponse(
                {"error": "Unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"}
            )(scope, receive, send)
            return
        context = principal.set(who)
        try:
            await self.app(scope, receive, send)
        finally:
            principal.reset(context)
