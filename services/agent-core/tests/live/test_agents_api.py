"""Opt-in acceptance gate. Default CI performs no OpenAI requests."""

import os

import pytest


@pytest.mark.skipif(os.environ.get("AGENT_CORE_LIVE") != "1", reason="live acceptance is opt-in")
def test_agents_api_live_acceptance():
    pytest.fail(
        "AC13 unverified: T01 must amend create_session for initial input with environment=none, "
        "pin openai==3.42.0, and integrate worker/T04/scoped cleanup before live smoke is possible"
    )
