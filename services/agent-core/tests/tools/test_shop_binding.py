import hashlib
import json

import pytest

from app.tools.shop_bindings import Binding, Bindings
from tests.mcp.support import SCOPE


def binding():
    return Binding(
        id="demo",
        version="1",
        tenant_id="tenant-a",
        user_id="alice",
        shop_id="shop-a",
        phone="+84900000001",
        shop_key="shopee-open-platform:1001",
        coverage_start="2026-09-01",
    )


def test_binding_digest_pins_identity_and_coverage():
    value = binding()
    expected = hashlib.sha256(
        json.dumps(value.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert value.reference.digest == expected
    assert Bindings([value]).resolve(value.reference, SCOPE) == value
    with pytest.raises(ValueError):
        Bindings([value.model_copy(update={"coverage_start": "2026-08-01"})]).resolve(
            value.reference, SCOPE
        )
    with pytest.raises(ValueError):
        Bindings([value]).resolve(value.reference, SCOPE.model_copy(update={"user_id": "bob"}))
    assert value.phone not in repr(value)


def test_duplicate_binding_versions_rejected():
    with pytest.raises(ValueError):
        Bindings([binding(), binding()])


def test_remote_profile_requires_binding_and_scope_before_query():
    import asyncio

    from app.tools.bridge import MCPToolBridge
    from app.tools.credentials import Credentials
    from tests.mcp.support import KEY, HistoryStub, config
    from tests.tools.test_bridge import pending
    from tests.tools.test_shop_adapter import QueryClient

    client = QueryClient()
    snapshot = config().model_copy(
        update={
            "mcp_profile": "shop-data-read-v1",
            "data_mcp_url": "http://srv-captain--shop-data-mcp:8000/mcp",
            "knowledge_mcp_url": "http://srv-captain--agent-core:8000/mcp/knowledge-memory",
            "shop_data_binding": binding().reference,
        }
    )
    repo = HistoryStub()
    for cid, conversation in repo.conversations.items():
        repo.conversations[cid] = conversation.model_copy(update={"config": snapshot})
    bridge = MCPToolBridge(
        repository=repo,
        credentials=Credentials(KEY),
        client=client,
        compatible_remote_profiles=frozenset({"shop-data-read-v1"}),
        shop_data_bindings=Bindings([binding()]),
    )
    result = asyncio.run(
        bridge.execute(
            SCOPE,
            "conv-a",
            snapshot,
            pending(
                arguments={"sku": "SHIRT-M", "start_date": "2026-10-24", "end_date": "2026-10-30"}
            ),
        )
    )
    assert result.error is None
    assert len(client.calls) == 1
    with pytest.raises(ValueError):
        bridge.validate_profile(snapshot.model_copy(update={"shop_data_binding": None}))
