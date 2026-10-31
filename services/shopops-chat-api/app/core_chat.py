"""Durable application outbox and polling adapter; Core owns execution and history."""

import asyncio
import contextlib
import hashlib
import json
import uuid
from contextlib import asynccontextmanager

import anyio
import httpx
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.agent_core import CoreAPI, CoreError, identifier
from app.chat import sse
from app.contracts import STREAM_RESPONSES, Artifact, ChatEvent, Message, MessageInput, Source
from app.demo_auth import DemoAuth, PhoneInput
from app.settings import Settings
from app.store import BusyError, CoreStore


class CoreChat:
    def __init__(self, settings: Settings, transport=None) -> None:
        self.config = settings
        self.store = CoreStore(settings.database)
        self.auth = DemoAuth(self.store)
        self.api = CoreAPI(settings.core_url, transport)
        self.poll_budget = 260
        self.heartbeat_interval = 10

    async def db(self, method: str, *args, **kwargs):
        return await asyncio.to_thread(lambda: getattr(self.store, method)(*args, **kwargs))

    def namespace(self, who: dict) -> tuple[str, str, str]:
        configuration = json.dumps(
            [self.config.core_url.rstrip("/"), self.config.core_shop, self.config.core_revision]
        )
        actor = json.dumps([who["tenant_id"], who["user_id"]])
        return hashlib.sha256((actor + configuration).encode()).hexdigest(), actor, configuration

    async def space(self, who: dict) -> dict:
        return await self.db("space", *self.namespace(who))

    async def provision(self, who: dict, space: dict) -> None:
        token, ns = who["core_token"], space["namespace"]
        if not space["orchestrator"]:
            result = await self.api.request(
                "POST",
                f"shops/{identifier(self.config.core_shop)}/orchestrator",
                token,
                {"template_id": "shopops", "config_revision": self.config.core_revision},
            )
            space["orchestrator"] = identifier(result["orchestrator_id"])
            if result.get("config_revision") != self.config.core_revision:
                raise CoreError("Configuration conflict")
            await self.db("core_space_update", ns, orchestrator=space["orchestrator"])

    async def ensure(self, who: dict, space: dict) -> str:
        await self.provision(who, space)
        token, ns = who["core_token"], space["namespace"]
        if not space["conversation"]:
            result = await self.api.request(
                "POST",
                f"shops/{identifier(self.config.core_shop)}/conversations",
                token,
                {
                    "orchestrator_id": space["orchestrator"],
                    "client_conversation_id": space["client_id"],
                },
            )
            space["conversation"] = identifier(result["conversation_id"])
            await self.db("core_space_update", ns, conversation=space["conversation"])
        return identifier(space["conversation"])

    async def receipt(self, who: dict, space: dict, row: dict, owner: str) -> dict:
        if row["status"] != "pending" or row["run_id"]:
            return row
        ns, key = space["namespace"], row["client_id"]
        await self.db("core_update", ns, key, owner)
        conversation = await self.ensure(who, space)
        await self.db("core_update", ns, key, owner)
        result = await self.api.request(
            "POST",
            f"conversations/{conversation}/messages",
            who["core_token"],
            json.loads(row["payload"]) | {"client_message_id": key},
        )
        # polling_url is deliberately ignored; only validated local application IDs are used.
        values = {
            "run_id": identifier(result["run_id"]),
            "message_id": identifier(result["message_id"]),
        }
        await self.db("core_update", ns, key, owner, **values)
        return row | values

    async def run(self, who: dict, row: dict) -> dict:
        result = await self.api.request(
            "GET", f"runs/{identifier(row['run_id'])}", who["core_token"]
        )
        if result.get("run_id") != row["run_id"] or result.get("status") not in {
            "queued",
            "running",
            "waiting_tool",
            "reconciling",
            "completed",
            "failed",
            "cancelled",
        }:
            raise CoreError("Invalid Core run")
        return result

    async def project(self, who: dict, space: dict, message: dict, run: dict) -> dict:
        response = run.get("response")
        if (
            run["status"] != "completed"
            or not isinstance(response, dict)
            or response.get("kind") not in {"answer", "clarification", "cannot_answer"}
            or not isinstance(response.get("text"), str)
            or not response["text"].strip()
        ):
            raise CoreError("Invalid completed response")
        sources = [Source.model_validate(x).model_dump() for x in response.get("sources", [])]
        artifacts = []
        for item in await self.api.pages(
            f"runs/{identifier(run['run_id'])}/artifacts?limit=100", who["core_token"]
        ):
            if item.get("run_id") != run["run_id"] or ".." in item.get("filename", ""):
                raise CoreError("Invalid artifact")
            artifact = Artifact.model_validate(
                {k: v for k, v in item.items() if k != "run_id"}
            ).model_dump()
            identifier(artifact["id"])
            artifacts.append(artifact)
        mode = await self.db("core_output_mode", space["namespace"], run["run_id"])
        if mode == "report" and response["kind"] == "answer" and not artifacts:
            raise CoreError("Missing report artifact")
        if len(artifacts) > 2:
            raise CoreError("Too many artifacts")
        await self.db("core_save_artifacts", space["namespace"], run["run_id"], artifacts)
        return Message(
            id=message["id"],
            role="assistant",
            text=response["text"],
            created_at=message["created_at"],
            kind=response["kind"],
            sources=sources,
            artifacts=artifacts,
        ).model_dump(exclude_none=True)

    async def history(self, who: dict, space: dict) -> list[dict]:
        if not space["conversation"]:
            return []
        items = await self.api.pages(
            f"conversations/{identifier(space['conversation'])}/history?limit=100",
            who["core_token"],
        )
        messages, seen = [], set()
        previous_sequence = 0
        for item in items:
            if not isinstance(item.get("sequence"), int) or item["sequence"] <= previous_sequence:
                raise CoreError("History is not chronological")
            previous_sequence = item["sequence"]
            if item.get("conversation_id") != space["conversation"] or item["id"] in seen:
                raise CoreError("Invalid history")
            seen.add(item["id"])
        for item in items[-100:]:
            identifier(item["id"])
            message = Message(
                id=item["id"],
                role=item["role"],
                text=item["content"],
                created_at=item["created_at"],
            ).model_dump(exclude_none=True)
            if item["role"] == "assistant":
                run = await self.run(who, {"run_id": item["run_id"]})
                message = await self.project(who, space, item, run)
            messages.append(message)
        return messages

    async def finish(self, who, space, row, owner, run) -> dict | None:
        if run["status"] in {"failed", "cancelled"}:
            await self.db(
                "core_update", space["namespace"], row["client_id"], owner, status=run["status"]
            )
            return None
        if run["status"] != "completed":
            return None
        async with asyncio.timeout(30):
            messages = await self.api.pages(
                f"conversations/{identifier(space['conversation'])}/history?limit=100",
                who["core_token"],
            )
            found = [
                m for m in messages if m["run_id"] == row["run_id"] and m["role"] == "assistant"
            ]
            if len(found) != 1 or found[0].get("conversation_id") != space["conversation"]:
                raise CoreError("Missing canonical assistant message")
            message = await self.project(who, space, found[0], run)
        await self.db(
            "core_update", space["namespace"], row["client_id"], owner, status="completed"
        )
        return message

    async def resolve(self, who, space, row, owner) -> dict:
        if row["status"] == "completed":
            async with asyncio.timeout(30):
                run = await self.run(who, row)
                items = await self.api.pages(
                    f"conversations/{identifier(space['conversation'])}/history?limit=100",
                    who["core_token"],
                )
                found = [
                    m for m in items if m["run_id"] == row["run_id"] and m["role"] == "assistant"
                ]
                if len(found) != 1 or found[0].get("conversation_id") != space["conversation"]:
                    raise CoreError("Missing canonical reply")
                return await self.project(who, space, found[0], run)
        if row["status"] in {"failed", "cancelled"}:
            raise CoreError("Previous turn failed")
        row = await self.receipt(who, space, row, owner)
        delay = 0.5
        while True:
            await self.db("core_update", space["namespace"], row["client_id"], owner)
            run = await self.run(who, row)
            if run["status"] in {"completed", "failed", "cancelled"}:
                message = await self.finish(who, space, row, owner, run)
                if message is None:
                    raise CoreError("Turn failed")
                return message
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 2)

    async def stream(self, who, space, row, owner):
        ns, key = space["namespace"], row["client_id"]
        task = asyncio.create_task(self.resolve(who, space, row, owner))
        try:
            async with asyncio.timeout(self.poll_budget):
                while True:
                    done, _ = await asyncio.wait({task}, timeout=self.heartbeat_interval)
                    if done:
                        message = task.result()
                        break
                    if row["status"] == "pending":
                        await self.db("core_update", ns, key, owner)
                    yield ": heartbeat\n\n"
            yield sse({"type": "delta", "text": message["text"]})
            yield sse({"type": "done", "message": message})
        except (
            CoreError,
            httpx.HTTPError,
            HTTPException,
            ValueError,
            KeyError,
            StopIteration,
            BusyError,
            TimeoutError,
        ):
            yield sse(
                {
                    "type": "error",
                    "message": "The reply is unavailable. Load history before sending again.",
                }
            )
        finally:
            task.cancel()
            with anyio.CancelScope(shield=True):
                with contextlib.suppress(Exception, asyncio.CancelledError):
                    await task
                await self.db("core_release", ns, key, owner)


def create_core_app(config: Settings, transport=None) -> FastAPI:
    chat = CoreChat(config, transport)

    @asynccontextmanager
    async def lifespan(app):
        config.validate()
        await chat.db("initialize")
        try:
            yield
        finally:
            await chat.api.client.aclose()

    app = FastAPI(title="ShopOps Chat API", lifespan=lifespan)
    app.state.core_store = chat.store
    app.state.core_chat = chat
    bearer = HTTPBearer(auto_error=False)
    bearer_dependency = Depends(bearer)

    async def authorized(
        credentials: HTTPAuthorizationCredentials | None = bearer_dependency,
    ) -> dict:
        if credentials is None:
            raise HTTPException(401, "Unauthorized")
        who = await asyncio.to_thread(chat.auth.resolve, credentials.credentials)
        if config.core_shop not in who["shop_ids"]:
            raise HTTPException(404, "Not found")
        return who

    identity_dependency = Depends(authorized)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Invalid request."}, status_code=422)

    @app.exception_handler(ValueError)
    @app.exception_handler(KeyError)
    @app.exception_handler(CoreError)
    @app.exception_handler(httpx.HTTPError)
    @app.exception_handler(TimeoutError)
    async def unavailable(request, error):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"detail": "Core is temporarily unavailable. Load history to recover."}, status_code=503
        )

    @app.exception_handler(BusyError)
    async def busy(request, error):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            {"detail": "Resolve the previous turn by loading history."}, status_code=409
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/chat/auth/config")
    def auth_config() -> dict[str, str]:
        return {"mode": "demo_phone"}

    class LoginOutput(BaseModel):
        access_token: str
        expires_at: str

    @app.post("/api/chat/auth/demo-phone", response_model=LoginOutput)
    async def login(item: PhoneInput):
        who = chat.auth.identities.get(item.phone_number)
        if who is None:
            raise HTTPException(401, "Unauthorized")
        if config.core_shop not in who["shop_ids"]:
            raise HTTPException(404, "Not found")
        space = await chat.space(who)
        await chat.provision(who, space)
        return await asyncio.to_thread(chat.auth.login, item.phone_number)

    @app.post("/api/chat/auth/logout", status_code=204)
    async def logout(who=identity_dependency, credentials=bearer_dependency):
        await asyncio.to_thread(chat.auth.logout, credentials.credentials)

    @app.get("/api/chat/capabilities")
    def capabilities(who=identity_dependency) -> dict[str, bool]:
        return {"report_mode": True, "artifacts": True}

    @app.get("/api/chat/messages", response_model=list[Message], response_model_exclude_none=True)
    async def history(who=identity_dependency):
        async with asyncio.timeout(30):
            space = await chat.space(who)
            owner = str(uuid.uuid4())
            row = await chat.db("core_claim", space["namespace"], None, None, owner)
            if row:

                async def recover():
                    pending = await chat.receipt(who, space, row, owner)
                    run = await chat.run(who, pending)
                    if run["status"] not in {"completed", "failed", "cancelled"}:
                        raise BusyError("Pending run")
                    await chat.finish(who, space, pending, owner, run)

                task = asyncio.create_task(recover())
                try:
                    while not task.done():
                        done, _ = await asyncio.wait({task}, timeout=chat.heartbeat_interval)
                        if not done:
                            await chat.db(
                                "core_update", space["namespace"], row["client_id"], owner
                            )
                    task.result()
                finally:
                    task.cancel()
                    with anyio.CancelScope(shield=True):
                        with contextlib.suppress(Exception, asyncio.CancelledError):
                            await task
                        await chat.db("core_release", space["namespace"], row["client_id"], owner)
            return await chat.history(who, space)

    @app.post(
        "/api/chat/messages",
        response_class=StreamingResponse,
        response_model=ChatEvent,
        responses=STREAM_RESPONSES,
    )
    async def send(item: MessageInput, who=identity_dependency):
        space = await chat.space(who)
        key = item.client_message_id or str(uuid.uuid4())
        owner = str(uuid.uuid4())
        payload = json.dumps(
            {"content": item.text.strip(), "output_mode": item.output_mode}, sort_keys=True
        )
        try:
            row = await chat.db("core_claim", space["namespace"], key, payload, owner)
        except ValueError:
            raise HTTPException(409, "Idempotency conflict") from None
        return StreamingResponse(
            chat.stream(who, space, row, owner),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/chat/artifacts/{artifact_id}/content")
    async def download(artifact_id: str, who=identity_dependency):
        space = await chat.space(who)
        row = await chat.db("core_artifact", space["namespace"], artifact_id)
        if row is None:
            raise HTTPException(404, "Not found")
        artifact = row
        content = await chat.api.content(artifact, who["core_token"])
        return Response(
            content,
            media_type=artifact["media_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{artifact["filename"]}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    from app.navigation import add_navigation

    add_navigation(app, config, authorized, transport)
    return app
