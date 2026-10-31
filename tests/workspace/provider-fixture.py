"""Test-only provider transport. Never imported by a deployed service."""

import asyncio
import json

import httpx


class FixtureStream(httpx.AsyncByteStream):
    def __init__(self, owner, initial):
        self.owner = owner
        self.initial = initial

    async def __aiter__(self):
        owner = self.owner
        if self.initial:
            yield owner.event({"type": "agent.session.created", "session": {"id": "sess_fixture"}})
        turn_id = owner.turn_id
        yield owner.event(owner.turn_event("created", turn_id))
        text = owner.reply
        for offset in range(0, len(text), 48):
            await asyncio.sleep(0.06)
            yield owner.event({
                "type": "agent.session.turn.output_text.delta",
                "turn_id": turn_id, "item_id": f"msg_{turn_id}",
                "output_index": 0, "content_index": 0, "delta": text[offset:offset + 48],
            })
        yield owner.event({
            "type": "agent.session.turn.output_text.done", "turn_id": turn_id,
            "item_id": f"msg_{turn_id}", "output_index": 0, "content_index": 0, "text": text,
        })
        owner.status = "completed"
        yield owner.event(owner.turn_event("completed", turn_id))


class FixtureProvider:
    def __init__(self):
        self.number = 0
        self.turn_id = ""
        self.reply = ""
        self.status = "completed"

    @staticmethod
    def event(value):
        return f"data: {json.dumps(value)}\n\n".encode()

    @staticmethod
    def turn_event(kind, turn_id):
        return {"type": f"agent.session.turn.{kind}", "turn_id": turn_id,
                "turn": {"id": turn_id, "subagent_id": None}}

    def begin(self, prompt):
        self.number += 1
        self.turn_id = f"turn_fixture_{self.number}"
        self.status = "in_progress"
        self.reply = (
            "**Browser test fixture — no live shop data.**\n\n"
            "Your workspace keeps shop operations and this conversation independent.\n\n"
            "| Interface | Purpose |\n| --- | --- |\n"
            "| Shop browser | Review incidents |\n| Agent chat | Ask for context |\n\n"
            "[Open incidents](/shop/incidents) · [Open overview](/shop/overview)\n\n"
            "```text\ninspect → decide → verify\n```"
        )
        if "wide" in prompt.lower():
            self.reply += (
                "\n\n| Item | January | February | March | April | May | June |\n"
                "| --- | --- | --- | --- | --- | --- | --- |\n"
                "| Test fixture | Example | Example | Example | Example | Example | Example |\n\n"
                "```text\n" + "wide-code-fixture-" * 18 + "\n```"
            )
        if "long" in prompt.lower() or "slow" in prompt.lower():
            self.reply += "\n\n" + "\n\n".join(
                f"**Test note {index}.** This is scroll-test content, not a real recommendation."
                for index in range(1, 31)
            )

    async def __call__(self, request):
        path = request.url.path
        if request.method == "POST" and path.endswith("/sessions"):
            self.begin(json.loads(request.content)["input"])
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  stream=FixtureStream(self, True))
        if request.method == "GET" and path.endswith("/events"):
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  stream=FixtureStream(self, False))
        if request.method == "POST" and path.endswith("/events"):
            event = json.loads(request.content)["events"][0]
            if event["type"] == "agent.session.input.cancel":
                self.status = "cancelled"
            else:
                self.begin(event["input"][0]["content"][0]["text"])
            return httpx.Response(200, json={})
        if request.method == "GET" and path.endswith("/turns"):
            turns = [{"id": self.turn_id, "subagent_id": None, "status": self.status}] if self.turn_id else []
            return httpx.Response(200, json={"data": turns, "has_more": False})
        if request.method == "GET" and path.endswith("/sessions/sess_fixture"):
            return httpx.Response(200, json={"id": "sess_fixture", "status": "active"})
        if request.method == "GET" and path.endswith(f"/turns/{self.turn_id}"):
            return httpx.Response(200, json={"id": self.turn_id, "subagent_id": None, "status": self.status})
        if request.method == "GET" and path.endswith("/items"):
            return httpx.Response(200, json={"data": [], "has_more": False})
        raise AssertionError(f"Unexpected fixture provider request: {request.method} {path}")
