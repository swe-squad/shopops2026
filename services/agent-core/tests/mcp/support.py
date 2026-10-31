from datetime import UTC, datetime

from app.contracts.errors import NotFound
from app.contracts.identity import Scope
from app.contracts.models import ConfigSnapshot, Conversation, Message, Page

SCOPE = Scope(
    tenant_id="tenant-a",
    shop_id="shop-a",
    user_id="alice",
    permissions=frozenset({"conversation:write", "history:read"}),
)
OTHER_SHOP = Scope(
    tenant_id="tenant-a",
    shop_id="shop-b",
    user_id="alice",
    permissions=frozenset({"conversation:write", "history:read"}),
)
OTHER_USER = Scope(
    tenant_id="tenant-a",
    shop_id="shop-a",
    user_id="bob",
    permissions=frozenset({"conversation:write", "history:read"}),
)
KEY = "synthetic-test-key-with-at-least-32-bytes"
NOW = datetime(2026, 10, 25, tzinfo=UTC)


def config(base: str = "http://127.0.0.1:8000", **updates: object) -> ConfigSnapshot:
    return ConfigSnapshot(
        revision="returns-v1",
        template_id="shopops",
        model="fixture-only",
        knowledge_bundle="returns-v1",
        knowledge_version="1",
        mcp_profile="mock-v1",
        data_mcp_url=f"{base}/mcp/data",
        knowledge_mcp_url=f"{base}/mcp/knowledge-memory",
        capabilities=(
            "get_return_metrics",
            "get_review_summary",
            "search_knowledge",
            "get_conversation_history",
        ),
    ).model_copy(update=updates)


class HistoryStub:
    """Test-only scoped repository; T01 supplies the persistent implementation."""

    def __init__(self, snapshot: ConfigSnapshot | None = None) -> None:
        self.calls = 0
        self.conversations = {
            cid: Conversation(
                id=cid,
                scope=scope,
                orchestrator_id="orch",
                config=snapshot or config(),
                client_conversation_id=cid,
                created_at=NOW,
            )
            for cid, scope in (
                ("conv-a", SCOPE),
                ("conv-b", OTHER_SHOP),
                ("conv-bob", OTHER_USER),
            )
        }
        self.messages = {
            cid: [
                Message(
                    id=f"{cid}-{i}",
                    conversation_id=cid,
                    run_id="run",
                    role="user",
                    content=f"{cid} message {i}",
                    sequence=i,
                    created_at=NOW,
                )
                for i in range(1, 31)
            ]
            for cid in self.conversations
        }

    async def get_conversation(self, scope: Scope, conversation_id: str) -> Conversation:
        self.calls += 1
        conv = self.conversations.get(conversation_id)
        if conv is None or (conv.scope.tenant_id, conv.scope.shop_id, conv.scope.user_id) != (
            scope.tenant_id,
            scope.shop_id,
            scope.user_id,
        ):
            raise NotFound()
        return conv

    async def get_history(
        self, scope: Scope, conversation_id: str, after: str | None = None, limit: int = 50
    ) -> Page[Message]:
        await self.get_conversation(scope, conversation_id)
        messages = self.messages[conversation_id]
        start = next((i + 1 for i, m in enumerate(messages) if m.id == after), 0)
        items = messages[start : start + limit]
        more = start + limit < len(messages)
        return Page(items=tuple(items), next_cursor=items[-1].id if more else None)
