import pytest

from app.agents.capabilities import delegation_targets, select_tools
from app.agents.instructions import build_instructions
from app.contracts.errors import ConfigurationConflict
from app.contracts.runtime import RuntimeProfile
from app.tools.validation import definitions


def hosted(config):
    return config.model_copy(
        update={
            "runtime_profile": RuntimeProfile(
                profile_id="shopops-hosted-v1",
                environment_type="openai_hosted",
                bundle_id="shopops-hosted-v1",
                bundle_version="1.0.0",
                bundle_sha256="a" * 64,
                container_size="small",
                multi_agent_enabled=True,
                max_concurrent_subagents=2,
            )
        }
    )


def test_legacy_instructions_and_delegation_are_preserved(config):
    assert delegation_targets(config) == ()
    text = " ".join(build_instructions(config).split())
    assert "Không thực thi mã, shell" in text
    assert "data-analyst" not in text
    assert "/workspace/" not in text


def test_hosted_root_delegates_with_bounded_evidence_and_no_child_function_tools(config):
    config = hosted(config)
    assert delegation_targets(config) == ("data-analyst", "knowledge-analyst")
    text = " ".join(build_instructions(config).split())
    assert "create/message/wait" in text
    assert "Subagents cannot call function tools" in text
    assert "32 KiB" in text
    assert "same session and root turn" in text
    assert "sole writer" in text
    assert "/workspace/outputs/report.json" in text
    assert "/workspace/scratch/data-analyst/" in text
    assert "/workspace/scratch/knowledge-analyst/" in text
    assert "SKILL.md" in text and "summarize_returns.py" in text
    assert "tiếng Việt" in text
    assert config.data_mcp_url not in text
    assert config.knowledge_mcp_url not in text
    assert select_tools(config, definitions()) == select_tools(
        config.model_copy(update={"runtime_profile": RuntimeProfile()}), definitions()
    )


def test_hosted_allows_lightweight_responses_without_mandatory_report(config):
    text = " ".join(build_instructions(hosted(config)).split())
    assert "clarification, cannot_answer and simple text-only" in text
    assert "without metrics retrieval, a report or specialists" in text
    assert "output_mode=report" in text
    assert "kind=answer" in text
    assert "Do not claim" in text


def test_unknown_template_fails_before_delegation(config):
    config = hosted(config).model_copy(update={"template_id": "unapproved"})
    with pytest.raises(ConfigurationConflict):
        delegation_targets(config)
