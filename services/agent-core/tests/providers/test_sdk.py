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
