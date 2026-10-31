"""Real Core HTTP application/worker/SQLite, explicitly fake provider."""

import json
import os
import socket
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_demo_phone_auth import config, login


@pytest.mark.skipif(
    os.environ.get("AGENT_CORE_LOOPBACK") != "1",
    reason="Opt-in cross-service offline acceptance requires Core private dependencies",
)
def test_real_core_loopback_report_followup_clarification_and_restart(tmp_path):
    core = Path(__file__).resolve().parents[2] / "agent-core"
    executable = core / ".venv/bin/python"
    assert executable.exists(), "Install Core dependencies before loopback acceptance"
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        port = bound.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "AGENT_CORE_LIVE", "AGENT_CORE_LIVE_HOSTED"):
        env.pop(name, None)
    env["T09_CORE_DATA"] = str(tmp_path / "core")
    Path(env["T09_CORE_DATA"]).mkdir()
    with (tmp_path / "core.log").open("w") as log:
        process = subprocess.Popen(
            [
                str(executable),
                "-m",
                "uvicorn",
                "tests.chat_loopback:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=core,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            with httpx.Client(base_url=url, timeout=1, trust_env=False) as probe:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        if probe.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    assert process.poll() is None, "Core fixture failed; inspect local test log"
                    assert time.monotonic() < deadline, "Core fixture startup timed out"
                    time.sleep(0.05)
                settings = replace(
                    config(tmp_path), core_url=url, core_revision="returns-hosted-v1"
                )
                with TestClient(create_app(settings)) as c:
                    headers = login(c)
                    assert probe.get("/_fixture/stats").json() == {"sessions": 0, "turns": 0}

                    def send(text, key, mode="text"):
                        result = c.post(
                            "/api/chat/messages",
                            headers=headers,
                            json={"text": text, "client_message_id": key, "output_mode": mode},
                        )
                        events = [
                            json.loads(line[6:])
                            for line in result.text.splitlines()
                            if line.startswith("data: ")
                        ]
                        assert events[-1]["type"] == "done", events
                        return events[-1]["message"]

                    report = send("Synthetic report", "report", "report")
                    assert report["artifacts"] and report["kind"] == "answer"
                    artifact = report["artifacts"][0]
                    path = f"/api/chat/artifacts/{artifact['id']}/content"
                    assert c.get(path, headers=headers).status_code == 200
                    assert (
                        c.get("/api/chat/artifacts/foreign/content", headers=headers).status_code
                        == 404
                    )
                    assert send("Synthetic followup", "followup")["kind"] == "answer"
                    assert send("Synthetic clarification", "clarify")["kind"] == "clarification"
                    assert send("Synthetic report", "report", "report")["id"] == report["id"]
                    assert probe.get("/_fixture/stats").json() == {"sessions": 1, "turns": 3}
                    before = c.get("/api/chat/messages", headers=headers).json()
                    assert len(before) == 6
                    assert len({item["id"] for item in before}) == 6
                with TestClient(create_app(settings)) as restarted:
                    # The page did not reload; keep its token across backend restart.
                    after = restarted.get("/api/chat/messages", headers=headers)
                    assert after.status_code == 200
                    assert after.json() == before
                    assert probe.get("/_fixture/stats").json() == {"sessions": 1, "turns": 3}
                    assert restarted.get(path, headers=headers).status_code == 200
                process.terminate()
                process.wait(timeout=10)
                process = subprocess.Popen(
                    [
                        str(executable),
                        "-m",
                        "uvicorn",
                        "tests.chat_loopback:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                        "--no-access-log",
                    ],
                    cwd=core,
                    env=env,
                    stdout=log,
                    stderr=log,
                )
                deadline = time.monotonic() + 20
                while True:
                    try:
                        if probe.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    assert process.poll() is None
                    assert time.monotonic() < deadline
                    time.sleep(0.05)
                with TestClient(create_app(settings)) as both_restarted:
                    # The page did not reload; keep its token across backend restart.
                    result = both_restarted.get("/api/chat/messages", headers=headers)
                    assert result.status_code == 200
                    assert result.json() == before
                    assert both_restarted.get(path, headers=headers).status_code == 200
                    assert probe.get("/_fixture/stats").json() == {"sessions": 0, "turns": 0}
                    with both_restarted.app.state.core_store.connect() as db:
                        conversation = db.execute(
                            "SELECT conversation FROM core_spaces"
                        ).fetchone()[0]
                    for credential in ["local-bob", "local-carol"]:
                        denied = probe.get(
                            f"/api/v1/conversations/{conversation}/history",
                            headers={"Authorization": "Bearer " + credential},
                        )
                        assert denied.status_code == 404

        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture
def core_review_boundary(tmp_path):
    core = Path(__file__).resolve().parents[2] / "agent-core"
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        port = bound.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "AGENT_CORE_LIVE", "AGENT_CORE_LIVE_HOSTED"):
        env.pop(name, None)
    env["T09_CORE_DATA"] = str(tmp_path / "core-review")
    Path(env["T09_CORE_DATA"]).mkdir()
    with (tmp_path / "core-review.log").open("w") as log:
        process = subprocess.Popen(
            [
                str(core / ".venv/bin/python"),
                "-m",
                "uvicorn",
                "tests.chat_loopback:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=core,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            with httpx.Client(base_url=url, timeout=2, trust_env=False) as probe:
                deadline = time.monotonic() + 20
                while True:
                    try:
                        if probe.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    assert process.poll() is None
                    assert time.monotonic() < deadline
                    time.sleep(0.05)
                yield url, probe
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def data_events(response):
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


@pytest.mark.skipif(
    os.environ.get("AGENT_CORE_LOOPBACK") != "1", reason="Separate offline Core acceptance"
)
def test_review_r01_real_core_422_then_corrected_text(tmp_path, core_review_boundary):
    url, probe = core_review_boundary
    settings = replace(config(tmp_path), core_url=url, core_revision="returns-v1")
    with TestClient(create_app(settings)) as client:
        headers = login(client)
        client.app.state.core_chat.poll_budget = 10
        report = {
            "text": "Synthetic report",
            "client_message_id": "rejected-report",
            "output_mode": "report",
        }
        result = client.post("/api/chat/messages", headers=headers, json=report)
        assert [event["type"] for event in data_events(result)] == ["error"]
        assert probe.get("/_fixture/stats").json() == {"sessions": 0, "turns": 0}
        assert client.get("/api/chat/messages", headers=headers).json() == []
        with client.app.state.core_store.connect() as db:
            assert tuple(db.execute("SELECT status,run_id FROM core_outbox").fetchone()) == (
                "failed",
                None,
            )
        replay = client.post("/api/chat/messages", headers=headers, json=report)
        assert [event["type"] for event in data_events(replay)] == ["error"]
        result = client.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Synthetic text", "client_message_id": "corrected-text"},
        )
        assert data_events(result)[-1]["type"] == "done"
        assert probe.get("/_fixture/stats").json() == {"sessions": 1, "turns": 1}
        assert len(client.get("/api/chat/messages", headers=headers).json()) == 2


@pytest.mark.skipif(
    os.environ.get("AGENT_CORE_LOOPBACK") != "1", reason="Separate offline Core acceptance"
)
def test_review_r02_activation_before_first_message_rejects_mismatch(
    tmp_path, core_review_boundary
):
    url, probe = core_review_boundary
    settings = replace(config(tmp_path), core_url=url, core_revision="returns-hosted-v1")
    with TestClient(create_app(settings)) as client:
        headers = login(client)
        client.app.state.core_chat.poll_budget = 10
        assert probe.post("/_fixture/activate/returns-hosted-v2").status_code == 200
        headers = login(client)
        client.app.state.core_chat.poll_budget = 10
        result = client.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Synthetic text", "client_message_id": "wrong-revision"},
        )
        assert [event["type"] for event in data_events(result)] == ["error"]
        assert probe.get("/_fixture/revisions").json() == []
        with client.app.state.core_store.connect() as db:
            assert db.execute("SELECT conversation FROM core_spaces").fetchone()[0] is None
            assert tuple(db.execute("SELECT status,run_id FROM core_outbox").fetchone()) == (
                "failed",
                None,
            )
    # A definite configuration rejection also permits an explicit operator cutover.
    with TestClient(create_app(replace(settings, core_revision="returns-hosted-v2"))) as client:
        headers = login(client)
        client.app.state.core_chat.poll_budget = 10
        result = client.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Synthetic text", "client_message_id": "correct-revision"},
        )
        assert data_events(result)[-1]["type"] == "done"
        assert probe.get("/_fixture/revisions").json() == ["returns-hosted-v2"]


@pytest.mark.skipif(
    os.environ.get("AGENT_CORE_LOOPBACK") != "1", reason="Separate offline Core acceptance"
)
def test_review_r02_lost_conversation_receipt_replays_pinned_revision(
    tmp_path, core_review_boundary
):
    import asyncio

    url, probe = core_review_boundary
    settings = replace(config(tmp_path), core_url=url, core_revision="returns-hosted-v1")
    with TestClient(create_app(settings)) as client:
        headers = login(client)
        client.app.state.core_chat.poll_budget = 10
        chat = client.app.state.core_chat
        original = chat.api.request
        lost = []

        async def lose_after_create(method, path, token, body=None):
            result = await original(method, path, token, body)
            if path.endswith("/conversations") and not lost:
                lost.append(body)
                activated = await asyncio.to_thread(
                    probe.post, "/_fixture/activate/returns-hosted-v2"
                )
                assert activated.status_code == 200
                raise httpx.ReadTimeout("Synthetic lost conversation receipt")
            return result

        chat.api.request = lose_after_create
        body = {"text": "Synthetic text", "client_message_id": "stable-first"}
        result = client.post("/api/chat/messages", headers=headers, json=body)
        assert data_events(result)[-1]["type"] == "error"
        assert probe.get("/_fixture/revisions").json() == []
        deadline = time.monotonic() + 10
        while True:
            history = client.get("/api/chat/messages", headers=headers)
            if history.status_code == 200:
                break
            assert history.status_code == 409
            assert time.monotonic() < deadline
            time.sleep(0.05)
        assert len(history.json()) == 2
        assert probe.get("/_fixture/revisions").json() == ["returns-hosted-v1"]
        result = client.post("/api/chat/messages", headers=headers, json=body)
        assert data_events(result)[-1]["type"] == "done"
        followup = client.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Synthetic followup", "client_message_id": "followup"},
        )
        assert data_events(followup)[-1]["type"] == "done"
        assert probe.get("/_fixture/stats").json() == {"sessions": 1, "turns": 2}
