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
                    headers = login(restarted)
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
                    headers = login(both_restarted)
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
