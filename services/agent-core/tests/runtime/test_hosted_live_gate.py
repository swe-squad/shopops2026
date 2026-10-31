"""A legacy live opt-in must never enable a hosted sandbox."""

import json
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("live,hosted", [(None, None), ("1", None), (None, "1"), ("true", "1")])
def test_missing_gate_never_loads_credentials_or_creates_provider(tmp_path, live, hosted):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENAI_", "AGENT_CORE_"))}
    if live is not None:
        env["AGENT_CORE_LIVE"] = live
    if hosted is not None:
        env["AGENT_CORE_LIVE_HOSTED"] = hosted
    code = """
import json
from unittest.mock import patch
from scripts.hosted_smoke import run_hosted_smoke
with patch("dotenv.dotenv_values", side_effect=AssertionError("credentials read")):
    with patch("openai.AsyncOpenAI", side_effect=AssertionError("provider created")) as factory:
        result = run_hosted_smoke(credentials_file="must-not-be-opened")
        print(json.dumps({"result": result, "calls": factory.call_count}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["calls"] == 0
    assert output["result"]["status"] == "skipped"
    assert output["result"]["reason"] == "hosted_opt_in_required"


@pytest.mark.parametrize("flags", [[], ["--live"], ["--hosted"]])
def test_cli_requires_both_acknowledgements_before_importing_runner(flags, tmp_path):
    code = """
import runpy, sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"scripts.hosted_smoke", "openai", "dotenv"}:
            raise AssertionError("runner imported before gate")
sys.meta_path.insert(0, Guard())
runpy.run_module("scripts.demo_live_hosted", run_name="__main__")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, *flags, "--credentials-file", str(tmp_path / "absent")],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 2
    assert "required" in result.stderr
    assert "runner imported" not in result.stderr


def test_pytest_hosted_suite_is_skipped_with_only_legacy_gate():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENAI_", "AGENT_CORE_"))}
    env["AGENT_CORE_LIVE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/live/test_hosted_runtime.py", "-q"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 skipped" in result.stdout


def test_cli_explicit_flags_enable_runner_without_env_gates(monkeypatch, tmp_path):
    from scripts import demo_live_hosted, hosted_smoke

    for name in ("AGENT_CORE_LIVE", "AGENT_CORE_LIVE_HOSTED"):
        monkeypatch.delenv(name, raising=False)
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return {"status": "blocked", "cleanup": True, "local_cleanup": True}

    monkeypatch.setattr(hosted_smoke, "run_hosted_smoke", run)
    evidence = tmp_path / "aggregate.json"
    monkeypatch.setattr(sys, "argv", ["demo", "--live", "--hosted", "--evidence", str(evidence)])
    assert demo_live_hosted.main() == 2
    assert calls[0]["live"] is True and calls[0]["hosted"] is True
    assert json.loads(evidence.read_text())["status"] == "blocked"


def test_integrated_preflight_requires_credentials_before_constructing_provider(monkeypatch):
    import openai

    from scripts.hosted_smoke import run_hosted_smoke

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("OpenAI client constructed without credentials")

    monkeypatch.setattr(openai, "AsyncOpenAI", forbidden)
    result = run_hosted_smoke(live=True, hosted=True)
    assert result["status"] == "blocked"
    assert result["reason"] == "missing_key_or_model"
    assert result["cleanup"] and result["local_cleanup"]
