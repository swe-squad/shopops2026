"""Synthetic live acceptance; only aggregate evidence is returned or printed."""

import asyncio
import json
import os
import secrets
import shutil
import socket
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import uvicorn
from dotenv import dotenv_values
from fastapi import FastAPI

from app.config.settings import Settings
from app.contracts.identity import Scope
from app.main import create_app


@contextmanager
def serve(app: FastAPI, sock: socket.socket) -> Iterator[asyncio.AbstractEventLoop]:
    loop = []
    server = uvicorn.Server(
        uvicorn.Config(app, log_config=None, access_log=False, log_level="critical", loop="asyncio")
    )

    def run():
        async def start():
            loop.append(asyncio.get_running_loop())
            await server.serve(sockets=[sock])

        asyncio.run(start())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError("smoke_startup_failed")
            time.sleep(0.01)
        yield loop[0]
    finally:
        server.should_exit = True
        thread.join(30)
        if thread.is_alive():
            raise RuntimeError("smoke_shutdown_failed")


@contextmanager
def smoke_directory(evidence: dict) -> Iterator[str]:
    directory = tempfile.mkdtemp(prefix="agent-core-live-")
    try:
        yield directory
    finally:
        if evidence.get("cleanup"):
            shutil.rmtree(directory)
        else:
            # Keep durable recovery mappings if remote deletion could not be confirmed.
            evidence["recovery_directory"] = directory


async def cleanup_smoke(app: FastAPI, cid: str | None, run_ids: list[str]) -> dict:
    provider = app.state.provider
    worker = app.state.worker
    if worker is not None:
        await worker.stop()
        try:
            async with asyncio.timeout(5):
                while worker.heartbeat is not None:
                    await asyncio.sleep(0.01)
        except TimeoutError:
            pass
    sessions = set(provider.created_sessions)
    cleanup_ok = True
    if not sessions and run_ids and provider.last_http_status is None:
        try:
            async for session in provider.sessions.list(limit=100):
                if session.metadata.get("initial_run_id") in run_ids:
                    sessions.add(session.id)
        except Exception:
            cleanup_ok = False
    # Always attempt every known remote deletion, even if local deletion will be refused.
    for session_id in sessions:
        try:
            try:
                snapshot = await provider.inspect_session(session_id)
                if snapshot.root_turn_id and snapshot.root_status in {"running", "waiting_tool"}:
                    await provider.cancel_turn(session_id, snapshot.root_turn_id)
            except Exception:
                pass
            await provider.delete_session(session_id)
        except Exception:
            cleanup_ok = False
    local_ok = cid is None
    if cid and cleanup_ok:

        async def already_deleted(session_id: str) -> None:
            pass

        try:
            await app.state.repository.delete_conversation(
                Scope(tenant_id="tenant-a", shop_id="shop-a", user_id="alice"),
                cid,
                already_deleted,
            )
            local_ok = True
        except Exception:
            local_ok = False
    return {"cleanup": cleanup_ok, "local_cleanup": local_ok}


def run_live_smoke(
    *,
    model: str | None = None,
    credentials_file: str | None = None,
) -> dict:
    values = dotenv_values(credentials_file) if credentials_file else {}
    key = os.environ.get("OPENAI_API_KEY") or values.get("OPENAI_API_KEY")
    model = model or os.environ.get("OPENAI_MODEL") or values.get("OPENAI_MODEL")
    if not key or not model:
        return {"status": "failed", "error": "missing_key_or_model", "cleanup": True}
    evidence = {"status": "failed", "model": model, "completed_turns": 0, "cleanup": False}
    started = time.monotonic()
    with (
        smoke_directory(evidence) as directory,
        socket.socket() as sock,
    ):
        path = Path(directory)
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        base = f"http://127.0.0.1:{sock.getsockname()[1]}"
        registry = json.loads(Path("config/registry.json").read_text())
        registry["revisions"] = [
            registry["revisions"][0]
            | {
                "revision": "live-smoke-v1",
                "model": model,
                "data_mcp_url": base + "/mcp/data",
                "knowledge_mcp_url": base + "/mcp/knowledge-memory",
            }
        ]
        config_path = path / "registry.json"
        config_path.write_text(json.dumps(registry))
        settings = Settings.from_env(
            {
                "APP_ENV": "local",
                "AGENT_PROVIDER": "openai_agents",
                "AUTH_MODE": "fixture",
                "DATABASE_URL": f"sqlite:///{path / 'smoke.db'}",
                "CONFIG_PATH": str(config_path),
                "DATA_MCP_MODE": "mock",
                "DATA_MCP_URL": base + "/mcp/data",
                "KNOWLEDGE_MEMORY_MCP_URL": base + "/mcp/knowledge-memory",
                "MCP_TOKEN_SIGNING_KEY": secrets.token_urlsafe(32),
                "OPENAI_API_KEY": key,
                "OPENAI_MODEL": model,
            }
        )
        app = create_app(settings=settings)
        cid = None
        run_ids = []
        with (
            serve(app, sock) as loop,
            httpx.Client(
                base_url=base,
                headers={"Authorization": "Bearer local-alice"},
                timeout=10,
                trust_env=False,
            ) as client,
        ):
            try:
                provision = client.post(
                    "/api/v1/shops/shop-a/orchestrator",
                    json={"template_id": "shopops", "config_revision": "live-smoke-v1"},
                )
                provision.raise_for_status()
                conversation = client.post(
                    "/api/v1/shops/shop-a/conversations",
                    json={
                        "orchestrator_id": provision.json()["orchestrator_id"],
                        "client_conversation_id": secrets.token_hex(12),
                    },
                )
                conversation.raise_for_status()
                cid = conversation.json()["conversation_id"]
                questions = [
                    "Dùng get_return_metrics để kiểm tra SKU-A từ 2026-10-19 đến 2026-10-25. "
                    "Báo tỷ lệ hoàn kỳ này, kỳ trước và mức tăng theo điểm phần trăm. "
                    "Dẫn nguồn tool.",
                    "Vẫn SKU và khoảng ngày vừa rồi: gọi lại tool để xác minh. "
                    "Cho biết mức tăng "
                    "bao nhiêu điểm phần trăm. Dùng ngữ cảnh hội thoại, không hỏi lại SKU/ngày.",
                    "Tra search_knowledge với query sizing để giải thích chính sách xử lý "
                    "khi khách phàn nàn kích cỡ. Dẫn nguồn knowledge.",
                ]
                for index, question in enumerate(questions):
                    submitted = client.post(
                        f"/api/v1/conversations/{cid}/messages",
                        json={"client_message_id": f"smoke-{index}", "content": question},
                    )
                    submitted.raise_for_status()
                    run_id = submitted.json()["run_id"]
                    run_ids.append(run_id)
                    deadline = time.monotonic() + 190
                    while time.monotonic() < deadline:
                        response = client.get(f"/api/v1/runs/{run_id}")
                        response.raise_for_status()
                        run = response.json()
                        if run["status"] in {"completed", "failed", "cancelled"}:
                            if run["status"] != "completed":
                                raise RuntimeError(run.get("error") or "live_run_failed")
                            output = run["response"]
                            assert output["kind"] == "answer"
                            if index == 0:
                                assert "15" in output["text"] and "5" in output["text"]
                            if index == 1:
                                assert "10" in output["text"] or "mười" in output["text"].casefold()
                            expected = "data" if index < 2 else "knowledge"
                            assert any(source["type"] == expected for source in output["sources"])
                            evidence["completed_turns"] += 1
                            break
                        time.sleep(0.2)
                    else:
                        raise RuntimeError("live_poll_timeout")
                history = client.get(f"/api/v1/conversations/{cid}/history")
                history.raise_for_status()
                assert len(history.json()["items"]) == 6
                assert len(set(app.state.provider.created_sessions)) == 1
                evidence["same_session_followup"] = True
                evidence["metrics_and_knowledge_sources"] = True
                evidence["metrics_verified"] = True
                evidence["status"] = "passed"
            except Exception as error:
                # Never print exception bodies: they may contain credentials or user data.
                allowed = {
                    "provider_outcome_unknown",
                    "provider_request_rejected",
                    "invalid_output",
                    "live_run_failed",
                    "live_poll_timeout",
                }
                evidence["error"] = str(error) if str(error) in allowed else type(error).__name__
                evidence["provider_http_status"] = app.state.provider.last_http_status
                evidence["provider_error_fields"] = app.state.provider.last_error_fields
            finally:
                try:
                    evidence.update(
                        asyncio.run_coroutine_threadsafe(
                            cleanup_smoke(app, cid, run_ids), loop
                        ).result(timeout=60)
                    )
                    if not evidence["cleanup"]:
                        evidence["status"] = "failed"
                except Exception:
                    evidence["cleanup"] = False
                    evidence["status"] = "failed"
                    evidence["cleanup_error"] = "cleanup_failed"
    evidence["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return evidence
