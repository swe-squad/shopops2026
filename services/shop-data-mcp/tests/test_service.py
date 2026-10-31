"""Workflow unit checks with fake I/O; no live grant/database verification is implied."""

import asyncio
import json
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.auth import Principal
from app.service import DataService
from app.settings import Dataset, Settings, Shop


@pytest.fixture
def who() -> Principal:
    return Principal(
        subject="agent-a",
        shop="shop-a",
        scopes={"data:read", "data:refresh", "raw:read", "raw:request"},
    )


@pytest.fixture
def service() -> DataService:
    settings = Settings(
        control_dsn="postgresql://control@localhost/test",
        membership_dsn="postgresql://membership@localhost/test",
        public_url="https://mcp.example/mcp",
        datasets=[
            Dataset(
                id="orders",
                relation="analytics.orders",
                layer="mart",
                description="Summary",
                columns=["status"],
                resource="orders",
            ),
            Dataset(
                id="raw_orders",
                relation="source.orders",
                layer="raw",
                description="Raw",
                columns=["status", "created_at", "buyer_email"],
                time_column="created_at",
            ),
            Dataset(
                id="other_shop",
                relation="analytics.other",
                layer="mart",
                description="Unavailable to this shop",
                columns=["total"],
                resource="other-shop-orders",
            ),
        ],
        shops={
            "shop-a": Shop(
                query_dsn="postgresql://shop_a@localhost/test", datasets=["orders", "raw_orders"]
            )
        },
    )
    result = DataService(settings)
    result.db = AsyncMock()
    result.approval = AsyncMock()
    result.ingestion = AsyncMock()
    return result


@pytest.fixture
def grant(who: Principal) -> dict:
    now = datetime.now(UTC)
    return {
        "grant_id": "grant-a",
        "subject": who.subject,
        "shop_key": who.shop,
        "status": "approved",
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "datasets": {"raw_orders": ["status"]},
        "start": (now - timedelta(days=2)).isoformat(),
        "end": (now - timedelta(days=1)).isoformat(),
    }


def test_catalog_is_limited_to_configured_shop(service: DataService, who: Principal) -> None:
    assert [item.id for item in service.catalog(who)] == ["orders", "raw_orders"]


@pytest.mark.parametrize(
    "change",
    [
        {"subject": "other-agent"},
        {"shop_key": "shop-b"},
        {"grant_id": "other-grant"},
        {"status": "pending"},
        {"status": "denied"},
        {"status": "revoked"},
        {"expires_at": "2000-01-01T00:00:00Z"},
    ],
)
def test_grant_rejects_mismatch_revocation_or_expiry(
    service: DataService,
    who: Principal,
    grant: dict,
    change: dict,
) -> None:
    service.approval.request.return_value = grant | change
    with pytest.raises(ValueError):
        asyncio.run(service.grant(who, "grant-a"))


def test_grant_request_binds_verified_subject_and_shop(
    service: DataService,
    who: Principal,
    grant: dict,
) -> None:
    service.approval.request.return_value = grant
    assert asyncio.run(service.grant(who, "grant-a")) == grant
    service.approval.request.assert_awaited_once_with(
        "GET", "/v1/grants/grant-a", params={"subject": "agent-a", "shop_key": "shop-a"}
    )


def test_grant_is_checked_again_after_query_before_saving(
    service: DataService,
    who: Principal,
    grant: dict,
) -> None:
    service.approval.request.side_effect = [grant, grant | {"status": "revoked"}]
    service.db.query.return_value = {
        "columns": ["status"],
        "rows": [{"status": "ok"}],
        "truncated": False,
    }
    with pytest.raises(ValueError, match="Raw grant unavailable"):
        asyncio.run(service.analyze(who, "SELECT status FROM raw_orders", grant_id="grant-a"))
    service.db.query.assert_awaited_once()
    service.db.save.assert_not_awaited()


def test_saved_raw_source_rechecks_grant_on_read(
    service: DataService,
    who: Principal,
    grant: dict,
) -> None:
    service.db.read.return_value = {"grants": ["grant-a"], "payload": {}}
    service.approval.request.return_value = grant | {"status": "revoked"}
    with pytest.raises(ValueError, match="Raw grant unavailable"):
        asyncio.run(service.read(who, "result-a"))


def test_raw_query_without_grant_never_reaches_database(
    service: DataService,
    who: Principal,
) -> None:
    with pytest.raises(ValueError, match="Dataset unavailable"):
        asyncio.run(service.analyze(who, "SELECT * FROM raw_orders"))
    service.db.query.assert_not_awaited()
    service.db.save.assert_not_awaited()


def test_temporary_result_inherits_expiry_and_grant_dependencies(
    service: DataService,
    who: Principal,
    grant: dict,
) -> None:
    expiry = datetime.now(UTC) + timedelta(minutes=2)
    service.db.read.return_value = {
        "grants": ["grant-a"],
        "expires_at": expiry,
        "payload": {
            "columns": ["status"],
            "rows": [{"status": "ok"}],
            "grant_snapshots": {"grant-a": json.dumps(grant, sort_keys=True)},
        },
    }
    service.approval.request.return_value = grant
    service.db.query.return_value = {
        "columns": ["status"],
        "rows": [{"status": "ok"}],
        "truncated": False,
    }
    service.db.save.return_value = "result-b"
    result = asyncio.run(service.analyze(who, "SELECT * FROM temp", source_id="result-a"))
    assert result["result_id"] == "result-b"
    assert result["expires_at"] == expiry.isoformat()
    assert service.db.save.await_args.args[2:] == (["grant-a"], expiry)
    assert service.approval.request.await_count == 2


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-01-01", "2026-01-02"),
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        ("2026-01-02T00:00:00Z", "2026-01-01T00:00:00Z"),
    ],
)
def test_rejects_naive_empty_and_reversed_window(start: str, end: str) -> None:
    with pytest.raises(ValueError):
        DataService.window(start, end)


@pytest.mark.parametrize("case", ["old", "future", "resource", "key"])
def test_refresh_boundary_failures_do_not_reserve_or_submit(
    service: DataService,
    who: Principal,
    case: str,
) -> None:
    now = datetime.now(UTC)
    start, end = now - timedelta(days=2), now - timedelta(days=1)
    resource, key = "orders", "request-a"
    if case == "old":
        start = now - timedelta(days=31)
    elif case == "future":
        end = now + timedelta(days=1)
    elif case == "resource":
        resource = "other-shop-orders"
    elif case == "key":
        key = "../../escape"
    with pytest.raises(ValueError):
        asyncio.run(service.refresh(who, resource, start.isoformat(), end.isoformat(), key))
    service.db.reserve_refresh.assert_not_awaited()
    service.ingestion.request.assert_not_awaited()


def test_refresh_uses_verified_identity_and_persisted_idempotency(
    service: DataService,
    who: Principal,
) -> None:
    now = datetime.now(UTC)
    start, end = (now - timedelta(days=2)).isoformat(), (now - timedelta(days=1)).isoformat()
    service.db.reserve_refresh.return_value = {"operation_id": None}
    service.ingestion.request.return_value = {"operation_id": "op-a", "status": "queued"}
    result = asyncio.run(service.refresh(who, "orders", start, end, "request-a"))
    body = {
        "subject": "agent-a",
        "shop_key": "shop-a",
        "resource": "orders",
        "start": start,
        "end": end,
        "idempotency_key": "request-a",
    }
    service.db.reserve_refresh.assert_awaited_once_with(who, "request-a", body)
    service.ingestion.request.assert_awaited_once_with("POST", "/v1/refreshes", body=body)
    service.db.attach_operation.assert_awaited_once_with(who, "request-a", "op-a")
    assert result == {"operation_id": "op-a", "status": "queued"}


def test_existing_refresh_operation_does_not_resubmit(service: DataService, who: Principal) -> None:
    now = datetime.now(UTC)
    service.db.reserve_refresh.return_value = {"operation_id": "existing-op"}
    result = asyncio.run(
        service.refresh(
            who,
            "orders",
            (now - timedelta(days=2)).isoformat(),
            (now - timedelta(days=1)).isoformat(),
            "request-a",
        )
    )
    assert result["operation_id"] == "existing-op"
    service.ingestion.request.assert_not_awaited()


def test_missing_refresh_scope_fails_before_io(service: DataService, who: Principal) -> None:
    who.scopes.remove("data:refresh")
    with pytest.raises(ValueError, match="Permission denied"):
        asyncio.run(service.refresh(who, "orders", "invalid", "invalid", "request-a"))
    service.db.reserve_refresh.assert_not_awaited()
    service.ingestion.request.assert_not_awaited()


@pytest.mark.parametrize(
    "response",
    [
        {"operation_id": "../escape", "status": "queued"},
        {"operation_id": "", "status": "queued"},
        {"operation_id": "op-a", "status": "invented-success"},
        {"operation_id": "op-a"},
    ],
)
def test_refresh_rejects_invalid_upstream_metadata_before_attaching(
    service: DataService,
    who: Principal,
    response: dict,
) -> None:
    now = datetime.now(UTC)
    service.db.reserve_refresh.return_value = {"operation_id": None}
    service.ingestion.request.return_value = response
    with pytest.raises(ValueError, match="Invalid upstream operation"):
        asyncio.run(
            service.refresh(
                who,
                "orders",
                (now - timedelta(days=2)).isoformat(),
                (now - timedelta(days=1)).isoformat(),
                "request-a",
            )
        )
    service.db.attach_operation.assert_not_awaited()


def test_raw_grant_scope_is_required_before_approval_lookup(
    service: DataService,
    who: Principal,
) -> None:
    who.scopes.remove("raw:read")
    with pytest.raises(ValueError, match="Permission denied"):
        asyncio.run(service.grant(who, "grant-a"))
    service.approval.request.assert_not_awaited()


def test_raw_expiry_during_query_prevents_result_save(
    service: DataService,
    who: Principal,
    grant: dict,
) -> None:
    service.approval.request.side_effect = [
        grant,
        grant | {"expires_at": "2000-01-01T00:00:00Z"},
    ]
    service.db.query.return_value = {"columns": ["status"], "rows": [], "truncated": False}
    with pytest.raises(ValueError, match="Raw grant expired or invalid"):
        asyncio.run(service.analyze(who, "SELECT status FROM raw_orders", grant_id="grant-a"))
    service.db.query.assert_awaited_once()
    service.db.save.assert_not_awaited()


def test_raw_scope_change_during_query_prevents_result_save(
    service: DataService,
    who: Principal,
    grant: dict,
) -> None:
    service.approval.request.side_effect = [
        grant,
        grant | {"datasets": {"raw_orders": []}},
    ]
    service.db.query.return_value = {"columns": ["status"], "rows": [], "truncated": False}
    with pytest.raises(ValueError, match="Source grant changed"):
        asyncio.run(service.analyze(who, "SELECT status FROM raw_orders", grant_id="grant-a"))
    service.db.query.assert_awaited_once()
    service.db.save.assert_not_awaited()


def test_saved_raw_scope_change_prevents_materialized_data_release(
    service: DataService,
    who: Principal,
    grant: dict,
) -> None:
    service.db.read.return_value = {
        "grants": ["grant-a"],
        "payload": {"grant_snapshots": {"grant-a": json.dumps(grant, sort_keys=True)}},
    }
    service.approval.request.return_value = grant | {"datasets": {"raw_orders": []}}
    with pytest.raises(ValueError, match="Source grant changed"):
        asyncio.run(service.read(who, "result-a"))


def test_equivalent_timezone_refreshes_share_canonical_idempotency_body(
    service: DataService,
    who: Principal,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    start, end = now - timedelta(days=2), now - timedelta(days=1)
    offset = timezone(timedelta(hours=7))
    persisted = {}

    async def reserve(identity: Principal, key: str, body: dict) -> dict:
        assert identity == who
        assert key == "request-a"
        if persisted:
            assert persisted["body"] == body
        else:
            persisted.update(body=body, operation_id=None)
        return dict(persisted)

    async def attach(identity: Principal, key: str, operation_id: str) -> None:
        persisted["operation_id"] = operation_id

    service.db.reserve_refresh.side_effect = reserve
    service.db.attach_operation.side_effect = attach
    service.ingestion.request.return_value = {"operation_id": "operation-a", "status": "queued"}

    async def exercise() -> None:
        first = await service.refresh(
            who,
            "orders",
            start.astimezone(offset).isoformat(),
            end.astimezone(offset).isoformat(),
            "request-a",
        )
        repeated = await service.refresh(
            who,
            "orders",
            start.isoformat().replace("+00:00", "Z"),
            end.isoformat().replace("+00:00", "Z"),
            "request-a",
        )
        assert first["operation_id"] == repeated["operation_id"] == "operation-a"

    asyncio.run(exercise())
    bodies = [call.args[2] for call in service.db.reserve_refresh.await_args_list]
    assert bodies[0] == bodies[1]
    assert bodies[0]["start"] == start.isoformat()
    assert bodies[0]["end"] == end.isoformat()
    service.ingestion.request.assert_awaited_once()
