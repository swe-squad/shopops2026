import asyncio
import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.fixture import FixtureAuthenticator
from app.contracts.errors import ArtifactInvalid, ArtifactTransient, ArtifactUnavailable
from app.contracts.models import ApplicationResponse
from app.contracts.runtime import ArtifactRecord
from tests.runs.test_hosted_recovery import create, hosted


class Files:
    def __init__(self):
        self.calls = 0
        self.content = b"{}"
        self.error = None

    async def read_artifact(self, session_id, artifact_id, *, max_bytes):
        self.calls += 1
        if self.error:
            raise self.error
        return self.content


@pytest.fixture
def artifact_client(repo, registry):
    from app.api.router import build_api_router

    auth = FixtureAuthenticator()
    identity = next(v for v in auth.identities.values() if "history:read" in v.permissions)
    token = next(k for k, v in auth.identities.items() if v == identity)
    scope = identity.scope(sorted(identity.shop_ids)[0])

    async def prepare():
        hosted(registry)
        c = await create(repo, scope, "hosted-test")
        r = (await repo.enqueue_message(scope, c.id, "m", "hello")).run
        await repo.claim_next_run()
        await repo.save_session_mapping(r.id, "session")
        await repo.mark_submission(r.id, "submitted", "root")
        record = ArtifactRecord(
            id="11111111-1111-4111-8111-111111111111",
            provider_id="private",
            session_id="session",
            turn_id="root",
            path="/workspace/outputs/note.md",
            size=2,
            media_type="text/markdown",
            scope=scope,
            conversation_id=c.id,
            run_id=r.id,
            sha256=hashlib.sha256(b"{}").hexdigest(),
        )
        await repo.save_artifacts(scope, r.id, (record,))
        await repo.complete_run(r.id, "root", "item", ApplicationResponse(kind="answer", text="OK"))
        return record

    record = asyncio.run(prepare())
    files = Files()
    app = FastAPI()

    async def ready():
        return True

    app.include_router(build_api_router(repo, auth.authenticate, ready, artifact_provider=files))
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client, record, files, scope


def test_artifact_list_and_download(artifact_client):
    client, record, files, _ = artifact_client
    response = client.get(f"/api/v1/runs/{record.run_id}/artifacts")
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == record.id
    assert "private" not in response.text
    response = client.get(f"/api/v1/artifacts/{record.id}/content")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="note.md"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == b"{}"


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (ArtifactUnavailable(), 410),
        (ArtifactInvalid(), 502),
        (ArtifactTransient(), 503),
        (OSError("private"), 503),
    ],
)
def test_artifact_remote_errors(artifact_client, error, status):
    client, record, files, _ = artifact_client
    files.error = error
    assert client.get(f"/api/v1/artifacts/{record.id}/content").status_code == status


def test_artifact_digest_and_size(artifact_client):
    client, record, files, _ = artifact_client
    for invalid in (b"[]", b"oversized"):
        files.content = invalid
        assert client.get(f"/api/v1/artifacts/{record.id}/content").status_code == 502


def test_artifact_unknown_id_never_calls_provider(artifact_client):
    client, _, files, _ = artifact_client
    assert client.get("/api/v1/artifacts/foreign/content").status_code == 404
    assert files.calls == 0


@pytest.mark.parametrize("field", ["tenant_id", "shop_id", "user_id"])
def test_foreign_artifact_rejected_before_io(artifact_client, repo, field):
    from app.contracts.errors import NotFound

    _, record, files, scope = artifact_client

    async def scenario():
        foreign = scope.model_copy(update={field: "foreign"})
        with pytest.raises(NotFound):
            await repo.get_artifact(foreign, record.id)
        with pytest.raises(NotFound):
            await repo.list_artifacts(foreign, record.run_id)

    asyncio.run(scenario())
    assert files.calls == 0


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "/workspace/outputs/../secret.json",
        "/workspace/outputs/file.json\r\nX:bad",
        "/workspace/outputs/nested/file.json",
        "/workspace/outputs/a.json?x=y",
    ],
)
def test_unsafe_artifact_paths(path):
    from app.api.artifacts import safe_filename

    with pytest.raises(ArtifactInvalid):
        safe_filename(path, "application/json")
