"""Real Core/bridge HTTP fixture; only the paid model boundary is synthetic."""

import json
import os
import pickle
from dataclasses import replace
from pathlib import Path

from app.config.settings import Settings
from app.contracts.models import ApplicationResponse
from app.contracts.runtime import ProviderArtifact, ProviderEnvironment
from app.contracts.tools import PendingToolCall
from app.main import create_app
from app.providers.fake import FakeProvider, Scenario

ARGS = {"sku": "SHIRT-M", "start_date": "2026-10-24", "end_date": "2026-10-30"}


class PipelineProvider(FakeProvider):
    def __init__(self):
        super().__init__([Scenario(tool_name="get_return_metrics", arguments=ARGS)] * 20)
        self.payloads = {}
        self.report_turns = set()
        self.state_path = Path(os.environ["T10_PROVIDER_STATE"])
        if self.state_path.exists():
            # Harness-owned temporary file, never accepts untrusted provider state.
            self.sessions, self.payloads, self.report_turns = pickle.loads(
                self.state_path.read_bytes()
            )

    def _finish(self, session, response):
        super()._finish(session, response)
        self.state_path.write_bytes(
            pickle.dumps(
                (
                    {sid: replace(value, queues=[]) for sid, value in self.sessions.items()},
                    self.payloads,
                    self.report_turns,
                )
            )
        )

    async def create_session(self, config, correlation_id, *, initial_input=None):
        result = await super().create_session(config, correlation_id, initial_input=initial_input)
        environment = ProviderEnvironment(id="synthetic-" + result.id, state="connected")
        session = self._session(result.id)
        session.snapshot = session.snapshot.model_copy(update={"environment": environment})
        return result.model_copy(update={"environment": environment})

    async def submit_input(self, session_id, content, run_id):
        environment = self._session(session_id).snapshot.environment
        turn = await super().submit_input(session_id, content, run_id)
        session = self._session(session_id)
        session.snapshot = session.snapshot.model_copy(update={"environment": environment})
        if "report.json" in content:
            self.report_turns.add(turn)
        return turn

    async def submit_tool_result(self, call, result):
        session = self._session(call.session_id)
        session.deliveries[(call.turn_id, call.call_id)] = (call, result)
        if result.error:
            self._finish(session, ApplicationResponse(kind="cannot_answer", text=result.error))
            return
        if call.name == "get_return_metrics":
            pending = PendingToolCall(
                session_id=call.session_id,
                turn_id=call.turn_id,
                call_id="reviews-" + call.turn_id,
                name="get_review_summary",
                arguments=ARGS,
            )
            session.snapshot = session.snapshot.model_copy(update={"pending_calls": (pending,)})
            return
        if call.name == "get_review_summary":
            pending = PendingToolCall(
                session_id=call.session_id,
                turn_id=call.turn_id,
                call_id="knowledge-" + call.turn_id,
                name="search_knowledge",
                arguments={"query": "sizing"},
            )
            session.snapshot = session.snapshot.model_copy(update={"pending_calls": (pending,)})
            return
        results = {c.name: r for c, r in session.deliveries.values() if c.turn_id == call.turn_id}
        sources = tuple(s for r in results.values() for s in r.sources)
        report = {
            "schema_version": "1",
            "metrics": results["get_return_metrics"].data,
            "knowledge_findings": [
                {"reference": source.reference, "finding": "Check sizing guidance."}
                for source in results["search_knowledge"].sources
            ],
            "sources": [s.model_dump() for s in sources],
        }
        self.payloads[call.turn_id] = json.dumps(report).encode()
        self._finish(
            session,
            ApplicationResponse(
                kind="answer",
                text=json.dumps({name: r.data for name, r in results.items()}),
                sources=sources,
            ),
        )

    async def list_artifacts(self, session_id, turn_id):
        if turn_id not in self.report_turns or turn_id not in self.payloads:
            return ()
        return (
            ProviderArtifact(
                id=turn_id,
                session_id=session_id,
                turn_id=turn_id,
                path="/workspace/outputs/report.json",
                size=len(self.payloads[turn_id]),
                media_type="application/json",
            ),
        )

    async def read_artifact(self, session_id, artifact_id, *, max_bytes):
        return self.payloads[artifact_id]


provider = PipelineProvider()
app = create_app(settings=Settings.from_env(), provider=provider)


@app.get("/_fixture/stats")
def stats():
    return {
        "sessions": len(provider.sessions),
        "turns": sum(s.turn_count for s in provider.sessions.values()),
    }
