from fastapi import APIRouter, Depends, Query, Response

from app.api.orchestrators import shop_scope
from app.api.router import validate_cursor
from app.api.schemas import (
    ConversationInput,
    ConversationOutput,
    EnqueueOutput,
    HistoryOutput,
    MessageInput,
    MessageOutput,
)
from app.auth.dependencies import require_permission
from app.contracts.errors import NotFound
from app.contracts.identity import AuthContext
from app.contracts.repository import Repository


async def find_scoped(repository: Repository, auth: AuthContext, resource_id: str, *, run=False):
    for shop in sorted(auth.shop_ids):
        scope = auth.scope(shop)
        try:
            record = await (
                repository.get_run(scope, resource_id)
                if run
                else repository.get_conversation(scope, resource_id)
            )
            return scope, record
        except NotFound:
            continue
    raise NotFound()


def add_conversations(router: APIRouter, repository: Repository, identity) -> None:
    auth_dependency = Depends(identity)

    @router.post("/shops/{shop_id}/conversations", response_model=ConversationOutput)
    async def create(
        shop_id: str,
        body: ConversationInput,
        response: Response,
        auth: AuthContext = auth_dependency,
    ):
        scope = shop_scope(auth, shop_id)
        require_permission(auth, "conversation:write")
        result = await repository.create_conversation(
            scope, body.orchestrator_id, body.client_conversation_id
        )
        response.status_code = 201 if result.created else 200
        return ConversationOutput(conversation_id=result.record.id)

    @router.post(
        "/conversations/{conversation_id}/messages", status_code=202, response_model=EnqueueOutput
    )
    async def enqueue(
        conversation_id: str, body: MessageInput, auth: AuthContext = auth_dependency
    ):
        scope, _ = await find_scoped(repository, auth, conversation_id)
        require_permission(auth, "conversation:write")
        result = await repository.enqueue_message(
            scope,
            conversation_id,
            body.client_message_id,
            body.content,
            **({"output_mode": body.output_mode} if body.output_mode != "text" else {}),
        )
        return EnqueueOutput(
            message_id=result.message.id,
            run_id=result.run.id,
            polling_url=f"/api/v1/runs/{result.run.id}",
        )

    @router.get("/conversations/{conversation_id}/history", response_model=HistoryOutput)
    async def history(
        conversation_id: str,
        after: str | None = None,
        limit: int = Query(50, ge=1, le=100),
        auth: AuthContext = auth_dependency,
    ):
        scope, _ = await find_scoped(repository, auth, conversation_id)
        require_permission(auth, "history:read")
        page = await repository.get_history(scope, conversation_id, validate_cursor(after), limit)
        return HistoryOutput(
            items=[MessageOutput(**m.model_dump()) for m in page.items],
            next_cursor=page.next_cursor,
        )
