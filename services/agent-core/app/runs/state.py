from app.contracts.models import RunState

TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    "queued": frozenset({"running", "cancelled", "failed"}),
    "running": frozenset({"waiting_tool", "reconciling", "completed", "failed", "cancelled"}),
    "waiting_tool": frozenset({"running", "reconciling", "completed", "failed", "cancelled"}),
    "reconciling": frozenset({"running", "waiting_tool", "completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}
