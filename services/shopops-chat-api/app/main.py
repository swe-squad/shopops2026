import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.chat import Chat
from app.provider import AgentsProvider, ProviderError
from app.settings import Settings
from app.store import BusyError, Store


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=2000, pattern=r"[\s\S]*\S[\s\S]*")


class Message(BaseModel):
    id: int
    text: str
    role: Literal["user", "assistant"]
    created_at: str


def create_app(
    settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    config = settings or Settings.from_env()
    store = Store(config.database)
    provider = AgentsProvider(config.api_key, config.agent_id, transport)
    chat = Chat(store, provider)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            config.validate()
            await chat.db("initialize")
            yield
        finally:
            await provider.close()

    app = FastAPI(title="ShopOps Chat API", lifespan=lifespan)

    def authorize(authorization: Annotated[str | None, Header()] = None) -> None:
        expected = f"Bearer {config.token}"
        if (
            not config.token
            or not authorization
            or not secrets.compare_digest(authorization.encode(), expected.encode())
        ):
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/chat/messages", response_model=list[Message], dependencies=[Depends(authorize)])
    async def history() -> list[dict]:
        try:
            await chat.prepare()
        except (BusyError, ProviderError, httpx.HTTPError, TimeoutError) as _error:
            pass
        return await chat.db("history")

    @app.post("/api/chat/messages", dependencies=[Depends(authorize)])
    async def send(item: MessageInput) -> StreamingResponse:
        text = item.text.strip()
        try:
            prepared = await chat.prepare(text)
        except BusyError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ProviderError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        except (httpx.HTTPError, TimeoutError) as error:
            raise HTTPException(
                status_code=502, detail="Agent history is temporarily unavailable."
            ) from error
        pending, owner = prepared
        return StreamingResponse(
            chat.stream(pending, owner, text),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
