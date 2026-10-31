"""Allowlisted integration metadata rejects accidental payload disclosure."""

import pytest
from pydantic import ValidationError

from app.responses import ApprovalCreated, OperationStatus


def operation(**changes: object) -> dict:
    return {
        "operation_id": "operation-a",
        "subject": "agent-a",
        "shop_key": "shop-a",
        "status": "mart_ready",
        "coverage": {
            "dataset_ids": ["orders"],
            "start": "2026-10-01T00:00:00Z",
            "end": "2026-10-02T00:00:00Z",
            "collection_completed_at": "2026-10-02T00:01:00Z",
            "processing_completed_at": "2026-10-02T00:02:00Z",
        },
    } | changes


@pytest.mark.parametrize("status", ["pending", "denied"])
def test_approval_accepts_only_request_id_and_nonapproval_status(status: str) -> None:
    body = {"request_id": "request-a", "status": status}
    assert ApprovalCreated.model_validate(body).model_dump() == body


@pytest.mark.parametrize(
    "extra",
    [
        {"secret": "private credential"},
        {"raw_payload": {"buyer_email": "private"}},
        {"approval_url": "https://approval.example/private-link"},
    ],
)
def test_approval_rejects_every_extra_field(extra: dict) -> None:
    with pytest.raises(ValidationError):
        ApprovalCreated.model_validate({"request_id": "request-a", "status": "pending"} | extra)


@pytest.mark.parametrize("status", ["approved", "queued", "unknown"])
def test_request_creation_cannot_self_approve_or_invent_status(status: str) -> None:
    with pytest.raises(ValidationError):
        ApprovalCreated.model_validate({"request_id": "request-a", "status": status})


def test_operation_accepts_exact_coverage_contract() -> None:
    body = operation(error_code=None)
    assert OperationStatus.model_validate(body).model_dump(mode="json", exclude_unset=True) == body


def test_snapshot_completion_reports_revision_without_inventing_time_coverage() -> None:
    body = operation(
        status="snapshot_ready",
        coverage=None,
        refresh_mode="full_snapshot",
        applied_source_revision=7,
    )
    result = OperationStatus.model_validate(body)
    assert result.status == "snapshot_ready"
    assert result.coverage is None
    assert result.applied_source_revision == 7


@pytest.mark.parametrize(
    "changes",
    [
        {"applied_source_revision": None},
        {"applied_source_revision": -1},
        {"applied_source_revision": True},
        {"refresh_mode": None},
        {"coverage": operation()["coverage"]},
    ],
)
def test_snapshot_completion_rejects_missing_revision_or_claimed_interval(changes: dict) -> None:
    with pytest.raises(ValidationError):
        OperationStatus.model_validate(
            operation(
                status="snapshot_ready",
                coverage=None,
                refresh_mode="full_snapshot",
                applied_source_revision=7,
            )
            | changes
        )


@pytest.mark.parametrize(
    "status",
    [
        "queued",
        "collecting",
        "raw_available",
        "processing",
        "mart_ready",
        "failed",
        "cancelled",
        "partial",
    ],
)
def test_operation_accepts_documented_states_without_coverage(status: str) -> None:
    result = OperationStatus.model_validate(operation(status=status, coverage=None))
    assert result.status == status
    assert result.coverage is None


@pytest.mark.parametrize("field", ["secret", "raw_payload", "debug", "approval_url"])
def test_operation_rejects_unapproved_top_level_metadata(field: str) -> None:
    with pytest.raises(ValidationError):
        OperationStatus.model_validate(operation(**{field: "private secret"}))


@pytest.mark.parametrize("field", ["secret", "rows", "buyer_email", "payload"])
def test_operation_rejects_unapproved_nested_coverage_fields(field: str) -> None:
    body = operation()
    body["coverage"][field] = "private secret"
    with pytest.raises(ValidationError):
        OperationStatus.model_validate(body)


@pytest.mark.parametrize(
    "changes",
    [
        {"operation_id": "../escape"},
        {"status": "submitted"},
        {"error_code": "database password=private"},
        {"error_code": "x" * 65},
    ],
)
def test_operation_rejects_unknown_status_or_unsanitized_error_code(changes: dict) -> None:
    with pytest.raises(ValidationError):
        OperationStatus.model_validate(operation(**changes))


def test_operation_rejects_missing_coverage_bounds_and_oversized_metadata() -> None:
    for coverage in [
        {"dataset_ids": ["orders"], "start": "2026-10-01T00:00:00Z"},
        {"dataset_ids": ["orders"] * 101, "start": "start", "end": "end"},
        {"dataset_ids": ["orders"], "start": "x" * 65, "end": "end"},
    ]:
        with pytest.raises(ValidationError):
            OperationStatus.model_validate(operation(coverage=coverage))


@pytest.mark.parametrize(
    "field,value",
    [
        ("dataset_ids", ["orders;private"]),
        ("dataset_ids", ["Uppercase"]),
        ("dataset_ids", ["buyer@example.com"]),
        ("start", "private payload"),
        ("end", "2026-10-02T00:00:00"),
        ("collection_completed_at", "private credential"),
        ("processing_completed_at", "2026-10-02T00:02:00"),
    ],
)
def test_coverage_rejects_payload_text_and_naive_timestamps(field: str, value: object) -> None:
    body = operation()
    body["coverage"][field] = value
    with pytest.raises(ValidationError):
        OperationStatus.model_validate(body)
