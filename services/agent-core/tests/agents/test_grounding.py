import pytest

from app.agents.capabilities import select_tools
from app.agents.instructions import build_instructions
from app.contracts.errors import ConfigurationConflict, InvalidOutput
from app.contracts.models import Source
from app.contracts.tools import ToolDefinition
from app.providers.normalization import normalize_response


def test_rejects_fabricated_or_wrong_type_sources():
    payload = {
        "kind": "answer",
        "text": "Dữ liệu tổng hợp.",
        "sources": [{"type": "data", "reference": "known"}],
    }
    with pytest.raises(InvalidOutput):
        normalize_response(payload, ())
    with pytest.raises(InvalidOutput):
        normalize_response(payload, (Source(type="knowledge", reference="known"),))
    assert normalize_response(payload, (Source(type="data", reference="known"),)).kind == "answer"


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "answer", "text": ""},
        {"kind": "unknown", "text": "x"},
        {"kind": "answer", "text": "x" * 32001},
        {"kind": "answer", "text": "   "},
        {"kind": "answer", "text": "ok", "identity": "override"},
    ],
)
def test_invalid_output(payload):
    with pytest.raises(InvalidOutput):
        normalize_response(payload, ())


def test_profile_restricts_tools_and_context(config):
    safe = ToolDefinition(name="get_return_metrics", description="metrics", input_schema={})
    unsafe = ToolDefinition(name="shell", description="execute", input_schema={})
    assert select_tools(config, (safe, unsafe)) == (safe,)
    with pytest.raises(ConfigurationConflict):
        select_tools(config, ())
    text = build_instructions(config)
    assert config.data_mcp_url not in text
    assert config.knowledge_mcp_url not in text
