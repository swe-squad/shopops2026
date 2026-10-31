import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.contracts.errors import ConversationBusy
from scripts.live_smoke import cleanup_smoke


def test_remote_cleanup_continues_when_local_conversation_is_busy():
    provider = SimpleNamespace(
        created_sessions=["first", "second"],
        last_http_status=None,
        inspect_session=AsyncMock(side_effect=RuntimeError("inspection unavailable")),
        delete_session=AsyncMock(),
    )
    repository = SimpleNamespace(delete_conversation=AsyncMock(side_effect=ConversationBusy()))
    app = SimpleNamespace(
        state=SimpleNamespace(provider=provider, repository=repository, worker=None)
    )
    result = asyncio.run(cleanup_smoke(app, "conversation", []))
    assert result["cleanup"]
    assert not result["local_cleanup"]
    assert provider.delete_session.await_count == 2


def test_unconfirmed_remote_cleanup_preserves_recovery_directory():
    import shutil
    from pathlib import Path

    from scripts.live_smoke import smoke_directory

    provider = SimpleNamespace(
        created_sessions=["first", "second"],
        last_http_status=None,
        inspect_session=AsyncMock(side_effect=RuntimeError()),
        delete_session=AsyncMock(side_effect=[RuntimeError(), None]),
    )
    repository = SimpleNamespace(delete_conversation=AsyncMock())
    app = SimpleNamespace(
        state=SimpleNamespace(provider=provider, repository=repository, worker=None)
    )
    evidence = asyncio.run(cleanup_smoke(app, "conversation", []))
    assert not evidence["cleanup"]
    assert provider.delete_session.await_count == 2
    repository.delete_conversation.assert_not_called()
    try:
        with smoke_directory(evidence) as directory:
            Path(directory, "mapping").write_text("synthetic recovery state")
        assert Path(evidence["recovery_directory"], "mapping").exists()
    finally:
        shutil.rmtree(directory)
