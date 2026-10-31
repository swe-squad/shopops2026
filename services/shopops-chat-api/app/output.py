from app.provider import ProviderError


class TurnOutput:
    def __init__(self) -> None:
        self.root_id: str | None = None
        self.parts: dict[tuple[int, int, str], str] = {}
        self.seen: set[str] = set()

    @property
    def text(self) -> str:
        messages: dict[tuple[int, str], str] = {}
        for (index, _content_index, item_id), part in sorted(self.parts.items()):
            key = (index, item_id)
            messages[key] = messages.get(key, "") + part
        return "\n\n".join(messages.values())

    def apply(self, event: dict) -> str | None:
        event_id = event.get("event_id")
        if event_id and event_id in self.seen:
            return None
        if event_id:
            self.seen.add(event_id)
        kind = event.get("type", "")
        turn = event.get("turn", {})
        if kind in {"agent.session.turn.created", "agent.session.turn.in_progress"}:
            if turn.get("subagent_id", "unknown") is None:
                self.root_id = turn["id"]
        if kind in {"error", "agent.session.failed", "agent.session.environment.failed"}:
            raise ProviderError("The agent could not complete this request.")
        if kind == "agent.session.requires_action":
            raise ProviderError("The orchestrator needs an action this chat cannot provide.")
        if kind in {"agent.session.turn.failed", "agent.session.turn.cancelled"}:
            if turn.get("subagent_id", "unknown") is None:
                return "failed"
        if kind == "agent.session.turn.completed" and turn.get("subagent_id", "unknown") is None:
            self.root_id = turn["id"]
            return "completed"
        if event.get("turn_id") != self.root_id or self.root_id is None:
            return None
        if kind in {"agent.session.turn.output_text.delta", "agent.session.turn.output_text.done"}:
            key = (event["output_index"], event["content_index"], event["item_id"])
            if kind.endswith(".delta"):
                self.parts[key] = self.parts.get(key, "") + event["delta"]
            else:
                # The final part is authoritative, even without any earlier deltas.
                self.parts[key] = event["text"]
            return "text"
        return None


def saved_text(items: list[dict]) -> str:
    messages: list[str] = []
    for item in items:
        if (
            item.get("type") != "message"
            or item.get("role") != "assistant"
            or item.get("status") != "completed"
        ):
            continue
        content = item.get("content")
        if not isinstance(content, list) or any(not isinstance(part, dict) for part in content):
            raise ProviderError("The agent returned invalid saved message content.")
        parts: list[str] = []
        for part in content:
            if part.get("type") == "output_text":
                if not isinstance(part.get("text"), str):
                    raise ProviderError("The agent returned invalid saved message text.")
                parts.append(part["text"])
        messages.append("".join(parts))
    return "\n\n".join(messages)
