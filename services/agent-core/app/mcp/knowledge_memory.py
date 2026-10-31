"""Immutable lexical knowledge and read-only, current-owner conversation history."""

import hashlib
import json
import re
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI

from app.contracts.models import Conversation, Source
from app.contracts.repository import Repository
from app.contracts.tools import ToolResult
from app.mcp.data import SERVICE_ROOT, build_mcp_app
from app.tools.credentials import Credentials


def _load_bundle(path: Path) -> tuple[dict, tuple[dict, ...]]:
    manifest = json.loads((path / "manifest.json").read_text())
    documents = manifest["documents"]
    checksum = hashlib.sha256(
        json.dumps(documents, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if checksum != manifest["checksum"]:
        raise ValueError("knowledge manifest checksum mismatch")
    chunks = []
    ids = set()
    for document in documents:
        file = (path / document["file"]).resolve()
        if file.parent != path.resolve() or document["id"] in ids:
            raise ValueError("invalid knowledge document")
        ids.add(document["id"])
        raw = file.read_bytes()
        if hashlib.sha256(raw).hexdigest() != document["sha256"]:
            raise ValueError("knowledge document checksum mismatch")
        text = raw.decode("utf-8")
        for offset in range(0, len(text), 4000):
            chunks.append(
                dict(
                    document_id=document["id"],
                    chunk_id=str(offset // 4000 + 1),
                    excerpt=text[offset : offset + 4000],
                    bundle_id=manifest["id"],
                    version=manifest["version"],
                )
            )
    return manifest, tuple(chunks)


def build_knowledge_memory_app(
    *,
    repository: Repository,
    credentials: Credentials,
    bundle_path: Path | None = None,
    allowed_origins: frozenset[str] = frozenset(),
) -> FastAPI:
    manifest, chunks = _load_bundle(bundle_path or SERVICE_ROOT / "knowledge/returns-v1")

    async def execute(conversation: Conversation, name: str, arguments: dict) -> ToolResult:
        observed = datetime.now(UTC).isoformat()
        if name == "search_knowledge":
            if (
                conversation.config.knowledge_bundle != manifest["id"]
                or conversation.config.knowledge_version != manifest["version"]
            ):
                return ToolResult(error="not_found")
            terms = set(re.findall(r"\w+", arguments["query"].casefold()))
            ranked = [
                (len(terms & set(re.findall(r"\w+", c["excerpt"].casefold()))), c) for c in chunks
            ]
            ranked.sort(key=lambda pair: (-pair[0], pair[1]["document_id"], pair[1]["chunk_id"]))
            matches = [chunk for score, chunk in ranked if score][: arguments["limit"]]
            sources = tuple(
                Source(
                    type="knowledge",
                    reference=(
                        f"knowledge:{manifest['id']}:{manifest['version']}:{c['document_id']}#{c['chunk_id']}"
                    ),
                )
                for c in matches
            )
            return ToolResult(data={"matches": matches}, sources=sources, observed_at=observed)
        # Foundation Repository uses opaque forward cursors. Retain a bounded window.
        window = deque(maxlen=arguments["limit"])
        after = None
        seen = set()
        boundary = arguments["before_sequence"]
        previous_sequence = 0
        while True:
            page = await repository.get_history(
                conversation.scope, conversation.id, after=after, limit=100
            )
            for message in page.items:
                if (
                    message.conversation_id != conversation.id
                    or message.sequence <= previous_sequence
                ):
                    raise ValueError("invalid scoped history")
                previous_sequence = message.sequence
                if boundary is not None and message.sequence >= boundary:
                    break
                window.append(message)
            if (
                page.next_cursor is None
                or not page.items
                or (boundary is not None and previous_sequence >= boundary)
            ):
                break
            if page.next_cursor in seen:
                raise ValueError("repeated history cursor")
            seen.add(page.next_cursor)
            after = page.next_cursor
        return ToolResult(
            data={"messages": [m.model_dump(mode="json") for m in window]},
            sources=tuple(
                Source(type="history", reference=f"history:{conversation.id}:{m.id}")
                for m in window
            ),
            observed_at=observed,
        )

    return build_mcp_app(
        repository=repository,
        credentials=credentials,
        audience="agent-core:knowledge-memory",
        names=frozenset({"search_knowledge", "get_conversation_history"}),
        handler=execute,
        allowed_origins=allowed_origins,
    )
