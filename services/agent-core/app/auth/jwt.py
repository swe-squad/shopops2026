import asyncio
from collections.abc import Callable
from urllib.parse import urlparse

import jwt
from pydantic import ValidationError

from app.auth.dependencies import Unauthorized
from app.contracts.identity import AuthContext


class JWTAuthenticator:
    """RS256 only; key URL comes from trusted deployment configuration, never a token."""

    def __init__(
        self,
        *,
        jwks_url: str,
        issuer: str,
        audience: str,
        jwks_loader: Callable[[], dict] | None = None,
    ) -> None:
        if urlparse(jwks_url).scheme != "https" or not issuer or not audience:
            raise ValueError("JWT requires HTTPS JWKS URL, issuer and audience")
        self.issuer = issuer
        self.audience = audience
        self.loader = jwks_loader
        self.client = jwt.PyJWKClient(jwks_url, timeout=5, lifespan=300)

    async def authenticate(self, token: str) -> AuthContext:
        return await asyncio.to_thread(self._authenticate, token)

    def _authenticate(self, token: str) -> AuthContext:
        try:
            if len(token) > 16384:
                raise Unauthorized()
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise Unauthorized()
            if self.loader is None:
                key = self.client.get_signing_key_from_jwt(token)
            else:
                candidates = [
                    k
                    for k in self.loader()["keys"]
                    if k.get("kid") == header["kid"]
                    and k.get("kty") == "RSA"
                    and k.get("use", "sig") == "sig"
                    and k.get("alg", "RS256") == "RS256"
                ]
                if len(candidates) != 1:
                    raise Unauthorized()
                key = jwt.PyJWK.from_dict(candidates[0], algorithm="RS256")
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={
                    "require": ["iss", "aud", "exp", "tenant_id", "sub", "shop_ids", "permissions"]
                },
            )
            for name in ("shop_ids", "permissions"):
                value = claims[name]
                if not isinstance(value, list) or any(
                    not isinstance(item, str) or not item.strip() or len(item) > 128
                    for item in value
                ):
                    raise Unauthorized()
            for name in ("tenant_id", "sub"):
                value = claims[name]
                if not isinstance(value, str) or not value.strip() or len(value) > 128:
                    raise Unauthorized()
            if type(claims["exp"]) not in (int, float):
                raise Unauthorized()
            return AuthContext(
                tenant_id=claims["tenant_id"],
                user_id=claims["sub"],
                shop_ids=frozenset(claims["shop_ids"]),
                permissions=frozenset(claims["permissions"]),
            )
        except jwt.PyJWTError, ValidationError, ValueError, KeyError, TypeError:
            raise Unauthorized() from None
