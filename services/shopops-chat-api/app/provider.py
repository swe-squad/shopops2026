import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import quote

import httpx


class ProviderError(Exception):
    pass


class RejectedError(ProviderError):
    """The server explicitly rejected input; retrying a new submission is safe."""


async def read_events(response: httpx.Response) -> AsyncIterator[dict]:
    """Decode SSE data blocks, including comments and multiline data frames."""
    data: list[str] = []
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
        elif not line and data:
            payload = "\n".join(data)
            data.clear()
            if payload == "[DONE]":
                return
            try:
                event = json.loads(payload)
            except ValueError as error:
                raise ProviderError("The agent returned an invalid event.") from error
            if not isinstance(event, dict):
                raise ProviderError("The agent returned an invalid event.")
            yield event
    if data:
        raise ProviderError("The agent stream ended inside an event.")


class AgentsProvider:
    def __init__(
        self, api_key: str, agent_id: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.agent_id = agent_id
        self.client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1/",
            headers={"Authorization": f"Bearer {api_key}", "OpenAI-Beta": "agents=v1"},
            timeout=httpx.Timeout(30, read=120),
            transport=transport,
        )

    async def close(self) -> None:
        await self.client.aclose()

    @staticmethod
    def path(session_id: str) -> str:
        return f"agents/sessions/{quote(session_id, safe='')}"

    @staticmethod
    async def check(response: httpx.Response) -> None:
        if not response.is_success:
            # Upstream response bodies can contain prompts or tool arguments. Never expose them.
            error_type = (
                RejectedError
                if response.status_code in {400, 401, 403, 404, 422, 429}
                else ProviderError
            )
            raise error_type(f"The agent request failed (HTTP {response.status_code}).")

    async def get(self, path: str, **params: str | int) -> dict:
        response = await self.client.get(path, params=params)
        await self.check(response)
        try:
            value = response.json()
        except ValueError as error:
            raise ProviderError("The agent returned an invalid response.") from error
        if not isinstance(value, dict):
            raise ProviderError("The agent returned an invalid response.")
        return value

    async def pages(self, path: str, **params: str | int) -> list[dict]:
        items: list[dict] = []
        cursors: set[str] = set()
        while True:
            page = await self.get(path, order="asc", limit=100, **params)
            data = page.get("data")
            if (
                not isinstance(data, list)
                or any(not isinstance(item, dict) for item in data)
                or not isinstance(page.get("has_more"), bool)
            ):
                raise ProviderError("The agent returned an invalid history page.")
            items.extend(data)
            if not page["has_more"]:
                return items
            cursor = page.get("last_id")
            if not isinstance(cursor, str) or not cursor or cursor in cursors:
                raise ProviderError("The agent returned an invalid history cursor.")
            cursors.add(cursor)
            params["after"] = cursor

    async def turns(self, session_id: str) -> list[dict]:
        turns = await self.pages(f"{self.path(session_id)}/turns")
        for turn in turns:
            if (
                not isinstance(turn.get("id"), str)
                or not turn["id"]
                or "subagent_id" not in turn
                or (turn["subagent_id"] is not None and not isinstance(turn["subagent_id"], str))
            ):
                raise ProviderError("The agent returned an invalid saved turn.")
        return turns

    async def cancel(self, session_id: str) -> None:
        response = await self.client.post(
            f"{self.path(session_id)}/events",
            json={"events": [{"type": "agent.session.input.cancel"}]},
        )
        await self.check(response)

    @asynccontextmanager
    async def stream(
        self,
        session_id: str | None,
        text: str,
        key: str,
        before_input: Callable[[], Awaitable[None]],
    ) -> AsyncIterator[AsyncIterator[dict]]:
        if session_id:
            method, path = "GET", f"{self.path(session_id)}/events?stream=true"
            body = None
        else:
            method, path = "POST", "agents/sessions"
            body = {
                "agent_id": self.agent_id,
                "environment": {"type": "none"},
                "input": text,
                "stream": True,
            }
            # Persist uncertain-send intent before a create request can reach the provider.
            await before_input()
        async with self.client.stream(
            method, path, json=body, headers={"Accept": "text/event-stream"}
        ) as response:
            await self.check(response)
            if session_id:
                # Opening the read stream is not an input attempt; only the following POST is.
                await before_input()
                submitted = await self.client.post(
                    f"{self.path(session_id)}/events",
                    headers={"Idempotency-Key": key},
                    json={
                        "events": [
                            {
                                "type": "agent.session.input.message",
                                "input": [
                                    {
                                        "role": "user",
                                        "content": [{"type": "input_text", "text": text}],
                                    }
                                ],
                            }
                        ]
                    },
                )
                await self.check(submitted)
            yield read_events(response)
