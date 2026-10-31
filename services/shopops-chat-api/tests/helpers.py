import json

import httpx

from app.main import create_app
from app.settings import Settings

HEADERS = {"Authorization": "Bearer test-token"}


def turn(kind="created", turn_id="turn_1", subagent_id=None):
    return {
        "type": f"agent.session.turn.{kind}",
        "turn_id": turn_id,
        "turn": {"id": turn_id, "subagent_id": subagent_id},
    }


def text(value, kind="delta", turn_id="turn_1", index=0):
    return {
        "type": f"agent.session.turn.output_text.{kind}",
        "turn_id": turn_id,
        "item_id": "msg_1",
        "output_index": 0,
        "content_index": index,
        "delta" if kind == "delta" else "text": value,
    }


def stream(*events):
    content = ": heartbeat\n\n" + "".join(f"data: {json.dumps(event)}\n\n" for event in events)
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=content)


def configured_app(tmp_path, handler):
    return create_app(
        Settings(
            "test-token", "test-provider-key", "agent_orchestrator", str(tmp_path / "chat.db")
        ),
        httpx.MockTransport(handler),
    )


def events(response):
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
