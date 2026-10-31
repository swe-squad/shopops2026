"""Optional wire compatibility with T01's requested SDK pin, using no network."""

import asyncio
import json

import pytest

from app.providers.openai_agents import OpenAIAgentsProvider


def test_official_async_sdk_stream_surface():
    openai = pytest.importorskip("openai", reason="T01 must pin openai==3.42.0")
    httpx = pytest.importorskip("httpx2")

    async def exercise():
        def handle(request):
            assert request.url.path == "/v1/agents/sessions/session/events"
            assert request.headers["OpenAI-Beta"] == "agents=v1"
            frame = {
                "event_id": "evt",
                "session_id": "session",
                "turn_id": "turn",
                "type": "agent.session.turn.completed",
                "turn": {
                    "id": "turn",
                    "agent_id": "agent",
                    "created_at": 1,
                    "object": "agent.session.turn",
                    "session_id": "session",
                    "status": "completed",
                    "subagent_id": None,
                },
            }
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content="data: " + json.dumps(frame) + "\n\n",
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            async with openai.AsyncOpenAI(api_key="synthetic", http_client=http) as client:
                p = OpenAIAgentsProvider(client)
                async with p.stream_events("session") as stream:
                    await stream.wait_ready()
                    events = [event async for event in stream]
                assert len(events) == 1
                assert events[0].kind == "completed" and events[0].is_root

    asyncio.run(exercise())


def test_hosted_sdk_requests_inspection_artifacts_and_cleanup(config, monkeypatch):
    import httpx2 as httpx
    import openai

    import app.agents.runtime_bundle as bundles
    from tests.providers.test_hosted_lifecycle import artifact
    from tests.providers.test_hosted_runtime import approved_bundle, hosted_profile

    monkeypatch.setattr(bundles, "build_runtime_bundle", lambda profile: approved_bundle())

    async def exercise():
        requests = []

        def handle(request):
            path = request.url.path
            requests.append((request.method, path))
            assert request.headers["OpenAI-Beta"] == "agents=v1"
            if path == "/v1/agents/sessions" and request.method == "POST":
                payload = json.loads(request.content)
                assert payload["environment"]["network"] == {"access": "disabled"}
                assert payload["environment"]["plugins"][0]["source"]["type"] == "base64"
                assert payload["agent"]["multi_agent"]["max_concurrent_subagents"] == 2
                assert payload["input"] == "synthetic input"
                return httpx.Response(
                    200,
                    json={
                        "id": "session",
                        "environment": {"type": "openai_hosted", "id": "env"},
                        "metadata": {"initial_run_id": "run"},
                    },
                )
            if path == "/v1/agents/sessions/session" and request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "id": "session",
                        "status": "in_progress",
                        "environment": {"type": "openai_hosted", "id": "env"},
                        "metadata": {"initial_run_id": "run"},
                        "required_actions": [],
                    },
                )
            if path == "/v1/agents/environments/env":
                return httpx.Response(
                    200, json={"id": "env", "type": "openai_hosted", "status": "connected"}
                )
            if path == "/v1/agents/sessions/session/turns":
                return httpx.Response(
                    200,
                    json={
                        "data": [{"id": "turn", "subagent_id": None, "status": "completed"}],
                        "has_more": False,
                    },
                )
            if path == "/v1/agents/sessions/session/items":
                return httpx.Response(200, json={"data": [], "has_more": False})
            if path == "/v1/agents/sessions/session/artifacts":
                return httpx.Response(200, json={"data": [artifact()], "has_more": False})
            if path == "/v1/agents/sessions/session/artifacts/artifact" and request.method == "GET":
                return httpx.Response(200, json=artifact())
            if path == "/v1/agents/sessions/session/artifacts/artifact/content":
                return httpx.Response(200, content=b'{"ok":true}')
            if request.method == "DELETE":
                return httpx.Response(200, json={"id": path.rsplit("/", 1)[1], "deleted": True})
            raise AssertionError(f"Unexpected SDK request: {request.method} {path}")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            async with openai.AsyncOpenAI(api_key="synthetic", http_client=http) as client:
                provider = OpenAIAgentsProvider(client)
                assert provider.client.max_retries == 0
                created = await provider.create_session(
                    config.model_copy(update={"runtime_profile": hosted_profile()}),
                    "run",
                    initial_input="synthetic input",
                )
                assert created.environment.state == "provisioning"
                inspected = await provider.inspect_session("session")
                assert inspected.environment.state == "connected"
                assert inspected.root_turn_id == "turn"
                rows = await provider.list_artifacts("session", "turn")
                assert len(rows) == 1 and rows[0].media_type == "application/json"
                assert await provider.read_artifact("session", "artifact", max_bytes=20) == (
                    b'{"ok":true}'
                )
                await provider.delete_session("session")
        assert requests.count(("POST", "/v1/agents/sessions")) == 1
        assert requests[-2:] == [
            ("DELETE", "/v1/agents/sessions/session/artifacts/artifact"),
            ("DELETE", "/v1/agents/sessions/session"),
        ]

    asyncio.run(exercise())


def test_official_sdk_streaming_artifact_stops_oversize_transport():
    import httpx2 as httpx
    import openai

    from app.contracts.errors import ArtifactInvalid
    from tests.providers.test_hosted_lifecycle import artifact

    async def exercise():
        class Body(httpx.AsyncByteStream):
            read_count = 0
            closed = False

            async def __aiter__(self):
                for chunk in [b"1234", b"5678", b"never read"]:
                    self.read_count += 1
                    yield chunk

            async def aclose(self):
                self.closed = True

        body = Body()

        def handle(request):
            if request.url.path.endswith("/content"):
                return httpx.Response(200, stream=body)
            return httpx.Response(200, json=artifact(size_bytes=1))

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            async with openai.AsyncOpenAI(api_key="synthetic", http_client=http) as client:
                with pytest.raises(ArtifactInvalid):
                    await OpenAIAgentsProvider(client).read_artifact(
                        "session", "artifact", max_bytes=5
                    )
        assert body.read_count == 2
        assert body.closed

    asyncio.run(exercise())
