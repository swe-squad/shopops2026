import base64
import hashlib
import hmac
import json

import pytest

from app.contracts.identity import Scope
from app.tools.credentials import CredentialError, Credentials

KEY = "synthetic-test-key-with-at-least-32-bytes"
SCOPE = Scope(
    tenant_id="tenant-demo",
    shop_id="shop-a",
    user_id="user-a",
    permissions=frozenset({"data:read"}),
)


def signed(claims: dict, header: dict | None = None) -> str:
    def enc(value: dict) -> bytes:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=")

    payload = enc(header or {"alg": "HS256", "typ": "JWT"}) + b"." + enc(claims)
    sig = base64.urlsafe_b64encode(hmac.digest(KEY.encode(), payload, hashlib.sha256)).rstrip(b"=")
    return (payload + b"." + sig).decode()


def claims() -> dict:
    return dict(
        iss="agent-core",
        aud="agent-core:data",
        iat=100,
        exp=160,
        jti="test-id",
        tenant_id="tenant-demo",
        shop_id="shop-a",
        user_id="user-a",
        conversation_id="conv-a",
        permissions=["data:read"],
        config_revision="returns-v1",
    )


def test_issue_and_verify_full_scope() -> None:
    credentials = Credentials(KEY, clock=lambda: 100)
    token = credentials.issue(SCOPE, "conv-a", "returns-v1", "agent-core:data", {"data:read"})
    verified = credentials.verify(token, "agent-core:data", scope=SCOPE, conversation_id="conv-a")
    assert verified.scope == SCOPE
    assert verified.permissions == frozenset({"data:read"})
    assert verified.config_revision == "returns-v1"


@pytest.mark.parametrize(
    "patch",
    [
        {"aud": "agent-core:knowledge-memory"},
        {"iss": "attacker"},
        {"exp": 100},
        {"iat": 101},
        {"exp": 161},
        {"exp": True},
        {"permissions": "data:read"},
        {"permissions": [1]},
        {"tenant_id": ""},
        {"conversation_id": ""},
    ],
)
def test_reject_bad_claims(patch: dict) -> None:
    with pytest.raises(CredentialError):
        Credentials(KEY, clock=lambda: 100).verify(signed(claims() | patch), "agent-core:data")


@pytest.mark.parametrize("missing", list(claims()))
def test_all_claims_are_required(missing: str) -> None:
    value = claims()
    del value[missing]
    with pytest.raises(CredentialError):
        Credentials(KEY, clock=lambda: 100).verify(signed(value), "agent-core:data")


def test_signature_algorithm_and_scope_binding() -> None:
    credentials = Credentials(KEY, clock=lambda: 100)
    for token in (signed(claims(), {"alg": "none"}), signed(claims()) + "x", "broken"):
        with pytest.raises(CredentialError):
            credentials.verify(token, "agent-core:data")
    for kwargs in (
        {"conversation_id": "conv-b"},
        {"scope": SCOPE.model_copy(update={"shop_id": "shop-b"})},
    ):
        with pytest.raises(CredentialError):
            credentials.verify(signed(claims()), "agent-core:data", **kwargs)
    with pytest.raises(ValueError):
        Credentials("")
