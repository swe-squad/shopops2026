import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import anyio
import httpx

from app.output import TurnOutput, saved_text
from app.provider import AgentsProvider, ProviderError, RejectedError
from app.store import BusyError, Store


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class Chat:
    def __init__(self, store: Store, provider: AgentsProvider) -> None:
        self.store = store
        self.provider = provider

    async def db(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(lambda: getattr(self.store, method)(*args, **kwargs))

    async def recover(self, pending: dict, owner: str) -> bool:
        """Inspect saved outcomes only: never repeat input after an ambiguous disconnect."""
        if not pending["dispatched"]:
            await self.db("finish", pending["submission_key"], owner, None)
            return True
        session_id = pending["session_id"]
        if not session_id:
            return False
        session = await self.provider.get(self.provider.path(session_id))
        if session.get("status") == "failed":
            raise ProviderError(
                "The saved agent session has failed. Administrator recovery is required."
            )
        turn_id = pending["provider_turn_id"]
        if not turn_id:
            turns = await self.provider.turns(session_id)
            root_turns = [turn for turn in turns if turn.get("subagent_id", "unknown") is None]
            baseline = pending["baseline_turn_id"]
            if baseline:
                indices = [i for i, turn in enumerate(root_turns) if turn["id"] == baseline]
                if not indices:
                    return False
                root_turns = root_turns[indices[0] + 1 :]
            if not root_turns:
                return False
            turn_id = root_turns[0]["id"]
            await self.db("update", pending["submission_key"], owner, provider_turn_id=turn_id)
        turn = await self.provider.get(f"{self.provider.path(session_id)}/turns/{turn_id}")
        if turn.get("subagent_id", "unknown") is not None:
            raise ProviderError("The saved turn does not belong to the orchestrator.")
        if turn["status"] in {"failed", "cancelled"}:
            await self.db("finish", pending["submission_key"], owner, None)
            return True
        if turn["status"] != "completed":
            return False
        items = await self.provider.pages(f"{self.provider.path(session_id)}/turns/{turn_id}/items")
        text = saved_text(items)
        await self.db("finish", pending["submission_key"], owner, text or None)
        return True

    async def prepare(self, text: str | None = None) -> tuple[dict, str] | None:
        owner = str(uuid.uuid4())
        pending = await self.db("claim", text, owner)
        if not pending:
            return None
        if pending.get("recover"):
            try:
                with anyio.fail_after(60):
                    recovered = await self.recover(pending, owner)
            finally:
                await self.db("release", pending["submission_key"], owner)
            if not recovered:
                raise BusyError(
                    "The previous turn is still running or its outcome is uncertain. "
                    "Refresh history before sending again; input was not resent."
                )
            if text is None:
                return None
            return await self.prepare(text)
        return pending, owner

    async def heartbeat(self, key: str, owner: str) -> None:
        while True:
            await asyncio.sleep(10)
            await self.db("heartbeat", key, owner)

    async def stop(self, session_id: str | None) -> None:
        if session_id:
            with contextlib.suppress(httpx.HTTPError, ProviderError, TimeoutError):
                with anyio.move_on_after(5, shield=True):
                    await self.provider.cancel(session_id)

    async def stream(self, pending: dict, owner: str, text: str) -> AsyncIterator[str]:
        key, session_id = pending["submission_key"], pending["session_id"]
        output = TurnOutput()
        heartbeat = asyncio.create_task(self.heartbeat(key, owner))
        finished = False
        sent_text = ""
        try:
            if session_id:
                turns = await self.provider.turns(session_id)
                roots = [turn for turn in turns if turn.get("subagent_id", "unknown") is None]
                if roots and roots[-1]["status"] not in {"completed", "failed", "cancelled"}:
                    raise ProviderError("The orchestrator already has an active turn.")
                await self.db(
                    "update", key, owner, baseline_turn_id=roots[-1]["id"] if roots else ""
                )
            await self.db("update", key, owner, dispatched=1)
            async with self.provider.stream(session_id, text, key) as events:
                async for event in events:
                    if heartbeat.done():
                        heartbeat.result()
                    if event.get("type") == "agent.session.created":
                        session_id = event["session"]["id"]
                        await self.db("update", key, owner, session_id=session_id)
                    previous_root = output.root_id
                    change = output.apply(event)
                    if output.root_id and output.root_id != previous_root:
                        await self.db("update", key, owner, provider_turn_id=output.root_id)
                    if change == "text" and output.text.startswith(sent_text):
                        delta = output.text[len(sent_text) :]
                        if delta:
                            sent_text = output.text
                            yield sse({"type": "delta", "text": delta})
                    elif change == "failed":
                        await self.db("finish", key, owner, None)
                        finished = True
                        raise ProviderError("The orchestrator turn failed or was cancelled.")
                    elif change == "completed":
                        if not output.text.strip():
                            await self.db("finish", key, owner, None)
                            finished = True
                            raise ProviderError("The orchestrator completed without a text reply.")
                        message = await self.db("finish", key, owner, output.text)
                        finished = True
                        yield sse({"type": "done", "message": message})
                        return
            raise ProviderError("The agent stream ended before the orchestrator turn completed.")
        except RejectedError:
            await self.db("finish", key, owner, None)
            finished = True
            yield sse(
                {
                    "type": "error",
                    "message": "The agent rejected this request. Check configuration, then retry.",
                }
            )
        except (ProviderError, httpx.HTTPError, ValueError, KeyError, BusyError) as _error:
            # Keep provider bodies and internal exception details out of the browser.
            yield sse(
                {
                    "type": "error",
                    "message": "The reply was interrupted. Refresh history before trying again.",
                }
            )
        finally:
            heartbeat.cancel()
            with anyio.CancelScope(shield=True):
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await heartbeat
                if not finished:
                    await self.stop(session_id)
                await self.db("release", key, owner)
