"""Explicit opt-in live acceptance; default CI never calls OpenAI."""

import json
import os
from pathlib import Path

import pytest

from scripts.live_smoke import run_live_smoke


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("AGENT_CORE_LIVE") != "1", reason="live acceptance is opt-in")
def test_agents_api_live_acceptance():
    result = run_live_smoke()
    Path(".evidence").mkdir(exist_ok=True)
    Path(".evidence/live-acceptance.json").write_text(json.dumps(result) + "\n")
    assert result["status"] == "passed", result
    assert result["cleanup"]
    assert result["local_cleanup"]
    assert result["metrics_verified"]
    assert result["completed_turns"] == 3
    assert result["same_session_followup"]
