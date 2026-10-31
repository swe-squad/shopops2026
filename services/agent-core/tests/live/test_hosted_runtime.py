"""Separately gated hosted acceptance; synthetic inputs only."""

import json
import os
from pathlib import Path

import pytest


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("AGENT_CORE_LIVE") != "1" or os.environ.get("AGENT_CORE_LIVE_HOSTED") != "1",
    reason="hosted acceptance requires both explicit live gates",
)
def test_hosted_runtime_acceptance():
    from scripts.hosted_smoke import run_hosted_smoke

    result = run_hosted_smoke()
    evidence = Path(".evidence/live-hosted.json")
    evidence.parent.mkdir(exist_ok=True)
    evidence.write_text(json.dumps(result) + "\n")
    assert result["status"] == "passed", result
    assert result["cleanup"] and result["local_cleanup"]
    assert result["execution_verified"] and result["isolation_verified"]
