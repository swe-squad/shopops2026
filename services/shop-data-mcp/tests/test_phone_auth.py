"""Phone-only access: live membership, no JWT and no identity in tool arguments."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.auth import Authentication, principal
from app.database import Database
from tests import test_protocol

settings = test_protocol.settings

PHONE = "+84900000001"


@pytest.fixture
def phone_context(settings, monkeypatch):
    async def protected(request):
        who = principal.get()
        return JSONResponse({"shops": sorted(who.shops)})

    async def health(request):
        return JSONResponse({"status": "ok"})

    lookup = AsyncMock(return_value={"shop-a", "not-configured"})
    monkeypatch.setattr(Database, "authorized_shops", lookup, raising=False)
    app = Authentication(
        Starlette(routes=[Route("/protected", protected), Route("/health", health)]), settings
    )
    return SimpleNamespace(client=TestClient(app), lookup=lookup)


def test_phone_alone_resolves_current_configured_shops(phone_context):
    response = phone_context.client.get("/protected", headers={"X-Phone-Number": PHONE})
    assert response.status_code == 200
    assert response.json() == {"shops": ["shop-a"]}
    phone_context.lookup.assert_awaited_once_with(PHONE)
    with pytest.raises(LookupError):
        principal.get()


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer old-jwt"},
        {"X-Phone-Number": "0900000001"},
        {"X-Phone-Number": "+04900000001"},
        {"X-Phone-Number": PHONE + " "},
        {"X-Phone-Number": "+123"},
        {"X-Phone-Number": "+1234567890123456"},
        {"X-Phone-Number": "' OR true --"},
        [("X-Phone-Number", PHONE), ("X-Phone-Number", "+84900000002")],
        [(b"x-phone-number", b"\xff")],
    ],
)
def test_missing_malformed_or_duplicate_phone_is_denied_before_lookup(phone_context, headers):
    response = phone_context.client.get("/protected", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized"}
    assert "Bearer" not in response.headers.get("WWW-Authenticate", "")
    phone_context.lookup.assert_not_awaited()


@pytest.mark.parametrize("shops", [set(), {"not-configured"}])
def test_unknown_disabled_revoked_or_unconfigured_user_is_denied(phone_context, shops):
    phone_context.lookup.return_value = shops
    response = phone_context.client.get("/protected", headers={"X-Phone-Number": PHONE})
    assert response.status_code == 401
    assert PHONE not in response.text


def test_membership_is_rechecked_on_next_request(phone_context):
    headers = {"X-Phone-Number": PHONE}
    assert phone_context.client.get("/protected", headers=headers).status_code == 200
    phone_context.lookup.return_value = set()
    assert phone_context.client.get("/protected", headers=headers).status_code == 401
    assert phone_context.lookup.await_count == 2


def test_membership_outage_is_sanitized_and_never_allows_access(phone_context):
    phone_context.lookup.side_effect = RuntimeError("private database secret")
    response = phone_context.client.get("/protected", headers={"X-Phone-Number": PHONE})
    assert response.status_code == 503
    assert response.json() == {"error": "Access lookup unavailable"}


def test_health_does_not_require_phone_or_database(phone_context):
    assert phone_context.client.get("/health").status_code == 200
    phone_context.lookup.assert_not_awaited()
