from datetime import UTC, datetime
from types import SimpleNamespace as Record
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.router import build_api_router
from app.contracts.errors import (
    ConfigurationConflict,
    ConversationBusy,
    IdempotencyConflict,
    InvalidCursor,
    NotFound,
)
from app.contracts.identity import AuthContext
from app.contracts.models import Message, Page, RunEvent


class RepositoryFake:
    def __init__(self):
        self.orchestrators = {}
        self.conversations = {}
        self.runs = {}
        self.messages = {}
        self.events = {}

    async def provision(self, scope, template_id, config_revision):
        key = scope.tenant_id, scope.shop_id
        if key in self.orchestrators:
            record = self.orchestrators[key]
            if (record.template_id, record.config_revision) != (template_id, config_revision):
                raise ConfigurationConflict()
            return Record(record=record, created=False)
        record = Record(id=str(uuid4()), template_id=template_id, config_revision=config_revision)
        self.orchestrators[key] = record
        return Record(record=record, created=True)

    async def create_conversation(self, scope, orchestrator_id, client_conversation_id):
        if (
            self.orchestrators.get((scope.tenant_id, scope.shop_id), Record(id=None)).id
            != orchestrator_id
        ):
            raise NotFound()
        for record in self.conversations.values():
            if (
                record.scope.model_dump(exclude={"permissions"})
                == scope.model_dump(exclude={"permissions"})
                and record.client_id == client_conversation_id
            ):
                if record.orchestrator_id != orchestrator_id:
                    raise IdempotencyConflict()
                return Record(record=record, created=False)
        record = Record(
            id=str(uuid4()),
            scope=scope,
            client_id=client_conversation_id,
            orchestrator_id=orchestrator_id,
        )
        self.conversations[record.id] = record
        return Record(record=record, created=True)

    async def get_conversation(self, scope, conversation_id):
        record = self.conversations.get(conversation_id)
        if record is None or record.scope.model_dump(exclude={"permissions"}) != scope.model_dump(
            exclude={"permissions"}
        ):
            raise NotFound()
        return record

    async def enqueue_message(self, scope, conversation_id, client_message_id, content):
        await self.get_conversation(scope, conversation_id)
        for run in self.runs.values():
            if run.conversation_id == conversation_id:
                if run.client_id == client_message_id:
                    if run.content != content:
                        raise IdempotencyConflict()
                    return Record(message=self.messages[run.id], run=run, created=False)
                raise ConversationBusy()
        run = Record(
            id=str(uuid4()),
            conversation_id=conversation_id,
            client_id=client_message_id,
            content=content,
            state="queued",
            response=None,
            error=None,
            provider_turn_id="SECRET",
        )
        self.runs[run.id] = run
        message = Message(
            id=str(uuid4()),
            conversation_id=conversation_id,
            run_id=run.id,
            role="user",
            content=content,
            sequence=1,
            created_at=datetime.now(UTC),
            provider_item_id="SECRET",
        )
        self.messages[run.id] = message
        self.events[run.id] = RunEvent(
            id=str(uuid4()),
            run_id=run.id,
            sequence=1,
            type="raw SECRET",
            error="SECRET",
            provider_event_id="SECRET",
            created_at=datetime.now(UTC),
        )
        return Record(message=message, run=run, created=True)

    async def get_run(self, scope, run_id):
        run = self.runs.get(run_id)
        if run is None:
            raise NotFound()
        await self.get_conversation(scope, run.conversation_id)
        return run

    async def get_history(self, scope, conversation_id, after=None, limit=50):
        await self.get_conversation(scope, conversation_id)
        items = tuple(m for m in self.messages.values() if m.conversation_id == conversation_id)
        if after is not None and after not in {m.id for m in items}:
            raise InvalidCursor()
        return Page[Message](items=items if after is None else ())

    async def get_events(self, scope, run_id, after=None, limit=50):
        await self.get_run(scope, run_id)
        event = self.events[run_id]
        if after is not None and after != event.id:
            raise InvalidCursor()
        return Page[RunEvent](items=(event,) if after is None else ())


@pytest.fixture
def api():
    repository = RepositoryFake()
    identities = {
        "alice": AuthContext(
            tenant_id="t",
            user_id="alice",
            shop_ids={"s", "s2"},
            permissions={"orchestrator:provision", "conversation:write", "history:read"},
        ),
        "bob": AuthContext(
            tenant_id="t", user_id="bob", shop_ids={"s"}, permissions={"history:read"}
        ),
        "foreign": AuthContext(
            tenant_id="foreign", user_id="alice", shop_ids={"s"}, permissions={"history:read"}
        ),
        "other-shop": AuthContext(
            tenant_id="t", user_id="alice", shop_ids={"s2"}, permissions={"history:read"}
        ),
        "denied": AuthContext(tenant_id="t", user_id="alice", shop_ids={"s"}, permissions=set()),
    }

    async def authenticate(token):
        return identities[token]

    async def ready():
        return True

    app = FastAPI()
    app.include_router(build_api_router(repository, authenticate, ready))
    client = TestClient(app)
    client.headers["Authorization"] = "Bearer alice"
    return client, repository


def create(client):
    provision = client.post(
        "/api/v1/shops/s/orchestrator", json={"template_id": "shopops", "config_revision": "v1"}
    )
    assert provision.status_code == 201
    body = {"orchestrator_id": provision.json()["orchestrator_id"], "client_conversation_id": "c"}
    conversation = client.post("/api/v1/shops/s/conversations", json=body)
    assert conversation.status_code == 201
    assert client.post("/api/v1/shops/s/conversations", json=body).status_code == 200
    return conversation.json()["conversation_id"]


def test_provision_replay_and_conflict(api):
    client, _ = api
    body = {"template_id": "shopops", "config_revision": "v1"}
    first = client.post("/api/v1/shops/s/orchestrator", json=body)
    replay = client.post("/api/v1/shops/s/orchestrator", json=body)
    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json() == replay.json()
    assert (
        client.post(
            "/api/v1/shops/s/orchestrator", json={**body, "config_revision": "v2"}
        ).status_code
        == 409
    )
    foreign = client.post(
        "/api/v1/shops/s2/conversations",
        json={"orchestrator_id": first.json()["orchestrator_id"], "client_conversation_id": "c"},
    )
    assert foreign.status_code == 404


def test_message_replay_busy_conflict_and_sanitization(api):
    client, repository = api
    conversation = create(client)
    path = f"/api/v1/conversations/{conversation}/messages"
    body = {"client_message_id": "m", "content": "  hello  "}
    first = client.post(path, json=body)
    assert first.status_code == 202
    assert client.post(path, json={**body, "content": "hello"}).json() == first.json()
    busy = client.post(path, json={**body, "client_message_id": "new"})
    assert busy.status_code == 409 and busy.json()["error"]["code"] == "conversation_busy"
    conflict = client.post(path, json={**body, "content": "changed"})
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
    )
    polling = first.json()["polling_url"]
    repository.runs[first.json()["run_id"]].error = "SECRET"
    for url in [polling, polling + "/events", f"/api/v1/conversations/{conversation}/history"]:
        response = client.get(url)
        assert response.status_code == 200
        assert "SECRET" not in response.text
        assert "provider_" not in response.text
        for token in ["bob", "foreign", "other-shop"]:
            assert client.get(url, headers={"Authorization": f"Bearer {token}"}).status_code == 404
        assert client.get(url, headers={"Authorization": "Bearer denied"}).status_code == 403
    for query in ["limit=0", "limit=101", "after=broken", f"after={uuid4()}"]:
        assert client.get(polling + "/events?" + query).status_code == 422
    assert client.get("/api/v1/ready").status_code == 200


def test_openapi_has_only_public_fields(api):
    client, _ = api
    schema = client.get("/openapi.json").text
    for internal in ["provider_session_id", "provider_turn_id", "request_hash", "data_mcp_url"]:
        assert internal not in schema


@pytest.mark.parametrize("tool_name", ["get_return_metrics", "get_review_summary"])
def test_contract_tool_names_are_public(api, tool_name):
    client, repository = api
    conversation = create(client)
    response = client.post(
        f"/api/v1/conversations/{conversation}/messages",
        json={"client_message_id": "m", "content": "hello"},
    )
    run_id = response.json()["run_id"]
    repository.events[run_id] = repository.events[run_id].model_copy(
        update={"type": "tool_completed", "tool_name": tool_name, "error": None}
    )
    events = client.get(response.json()["polling_url"] + "/events")
    assert events.json()["items"][0]["tool_name"] == tool_name


def test_invalid_utf8_is_client_error(api):
    client, _ = api
    response = client.post(
        "/api/v1/conversations/c/messages",
        content=b"\xff",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
