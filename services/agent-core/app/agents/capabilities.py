"""Only pinned, approved read-only function tools enter agent context."""

from app.contracts.errors import ConfigurationConflict
from app.contracts.models import ConfigSnapshot
from app.contracts.tools import ToolDefinition

APPROVED_TOOLS = frozenset(
    {"get_return_metrics", "get_review_summary", "search_knowledge", "get_conversation_history"}
)


def select_tools(
    config: ConfigSnapshot, available: tuple[ToolDefinition, ...]
) -> tuple[ToolDefinition, ...]:
    requested = set(config.capabilities)
    names = [tool.name for tool in available]
    if not requested <= APPROVED_TOOLS or len(names) != len(set(names)):
        raise ConfigurationConflict()
    selected = tuple(tool for tool in available if tool.name in requested)
    if {tool.name for tool in selected} != requested or any(not t.read_only for t in selected):
        raise ConfigurationConflict()
    return selected


def delegation_targets(config: ConfigSnapshot) -> tuple[str, ...]:
    """Extension point: v1 never launches specialists."""
    return ()
