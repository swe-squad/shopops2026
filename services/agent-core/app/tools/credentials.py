"""Short lived HS256 service credentials; no tokens or payloads are logged."""

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Callable, Iterable
from uuid import uuid4

from pydantic import Field, ValidationError

from app.contracts.identity import Scope
from app.contracts.models import Record

AUDIENCES = frozenset({"agent-core:data", "agent-core:knowledge-memory"})
REQUIRED = frozenset(
    {
        "iss",
        "aud",
        "iat",
        "exp",
        "jti",
        "tenant_id",
        "shop_id",
        "user_id",
        "conversation_id",
        "permissions",
        "config_revision",
    }
)


class CredentialError(ValueError):
    def __init__(self) -> None:
        super().__init__("permission_denied")


class VerifiedCredential(Record):
    scope: Scope
    conversation_id: str = Field(min_length=1)
    config_revision: str = Field(min_length=1)
    permissions: frozenset[str]


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def _unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CredentialError()
        result[key] = value
    return result


class Credentials:
    def __init__(self, signing_key: str, *, clock: Callable[[], float] = time.time) -> None:
        if len(signing_key.encode()) < 32:
            raise ValueError("MCP_TOKEN_SIGNING_KEY must contain at least 32 bytes")
        self._key = signing_key.encode()
        self._clock = clock

    def issue(
        self,
        scope: Scope,
        conversation_id: str,
        config_revision: str,
        audience: str,
        permissions: Iterable[str],
    ) -> str:
        if audience not in AUDIENCES or not conversation_id or not config_revision:
            raise CredentialError()
        now = int(self._clock())
        permissions = frozenset(permissions)
        if not permissions <= scope.permissions:
            raise CredentialError()
        claims = {
            "iss": "agent-core",
            "aud": audience,
            "iat": now,
            "exp": now + 60,
            "jti": str(uuid4()),
            **scope.model_dump(),
            "conversation_id": conversation_id,
            "config_revision": config_revision,
            "permissions": sorted(permissions),
        }
        header = _encode(b'{"alg":"HS256","typ":"JWT"}')
        body = _encode(json.dumps(claims, separators=(",", ":")).encode())
        payload = f"{header}.{body}"
        return f"{payload}.{_encode(hmac.digest(self._key, payload.encode(), hashlib.sha256))}"

    def verify(
        self,
        token: str,
        audience: str,
        *,
        scope: Scope | None = None,
        conversation_id: str | None = None,
    ) -> VerifiedCredential:
        try:
            if len(token) > 8192:
                raise CredentialError()
            header, body, sig = token.split(".")
            metadata = json.loads(_decode(header), object_pairs_hook=_unique)
            if metadata != {"alg": "HS256", "typ": "JWT"}:
                raise CredentialError()
            expected = hmac.digest(self._key, f"{header}.{body}".encode(), hashlib.sha256)
            if not hmac.compare_digest(expected, _decode(sig)):
                raise CredentialError()
            claims = json.loads(_decode(body), object_pairs_hook=_unique)
            if not isinstance(claims, dict) or not REQUIRED <= claims.keys():
                raise CredentialError()
            now = self._clock()
            if (
                audience not in AUDIENCES
                or claims["iss"] != "agent-core"
                or claims["aud"] != audience
                or type(claims["iat"]) is not int
                or type(claims["exp"]) is not int
                or not claims["iat"] <= now < claims["exp"]
                or not 0 < claims["exp"] - claims["iat"] <= 60
            ):
                raise CredentialError()
            for name in (
                "jti",
                "tenant_id",
                "shop_id",
                "user_id",
                "conversation_id",
                "config_revision",
            ):
                if not isinstance(claims[name], str) or not claims[name].strip():
                    raise CredentialError()
            perms = claims["permissions"]
            if not isinstance(perms, list) or any(not isinstance(p, str) or not p for p in perms):
                raise CredentialError()
            verified = VerifiedCredential(
                scope=Scope(
                    **{k: claims[k] for k in ("tenant_id", "shop_id", "user_id")},
                    permissions=frozenset(perms),
                ),
                conversation_id=claims["conversation_id"],
                config_revision=claims["config_revision"],
                permissions=frozenset(perms),
            )
            if (scope is not None and not same_identity(scope, verified.scope)) or (
                conversation_id is not None and conversation_id != verified.conversation_id
            ):
                raise CredentialError()
            return verified
        except ValueError, TypeError, KeyError, AttributeError, binascii.Error, ValidationError:
            raise CredentialError() from None


def same_identity(left: Scope, right: Scope) -> bool:
    return (left.tenant_id, left.shop_id, left.user_id) == (
        right.tenant_id,
        right.shop_id,
        right.user_id,
    )
