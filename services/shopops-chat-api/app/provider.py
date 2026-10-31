import json
from collections.abc import AsyncIterator
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
        if response.is_error:
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
        value = response.json()
        if not isinstance(value, dict):
            raise ProviderError("The agent returned an invalid response.")
        return value

    async def pages(self, path: str, **params: str | int) -> list[dict]:
        items: list[dict] = []
        while True:
            page = await self.get(path, order="asc", limit=100, **params)
            items.extend(page["data"])
            if not page.get("has_more"):
                return items
            cursor = page.get("last_id")
            if not cursor or cursor == params.get("after"):
                raise ProviderError("The agent returned an invalid history cursor.")
            params["after"] = cursor

    async def turns(self, session_id: str) -> list[dict]:
        return await self.pages(f"{self.path(session_id)}/turns")

    async def cancel(self, session_id: str) -> None:
        response = await self.client.post(
            f"{self.path(session_id)}/events",
            json={"events": [{"type": "agent.session.input.cancel"}]},
        )
        await self.check(response)

    @asynccontextmanager
    async def stream(
        self, session_id: str | None, text: str, key: str
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
        async with self.client.stream(
            method, path, json=body, headers={"Accept": "text/event-stream"}
        ) as response:
            await self.check(response)
            if session_id:
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
