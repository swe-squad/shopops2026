"""Validate untrusted provider files against root-turn application evidence."""

import hashlib
import json
from uuid import uuid4

from pydantic import ValidationError

from app.api.artifacts import safe_filename
from app.contracts.errors import ArtifactInvalid
from app.contracts.models import ApplicationResponse, Run
from app.contracts.provider import AgentProvider
from app.contracts.report import RuntimeReport
from app.contracts.repository import Repository
from app.contracts.runtime import ArtifactRecord
from app.tools.validation import Metrics


def validate_report(payload: bytes, results: tuple) -> None:
    try:
        report = RuntimeReport.model_validate_json(payload)
        sources = {(s.type, s.reference) for r in results if not r.error for s in r.sources}
        claimed = {(s.type, s.reference) for s in report.sources}
        if not claimed <= sources or not {"data", "knowledge"} <= {t for t, _ in claimed}:
            raise ArtifactInvalid()
        if not report.knowledge_findings or any(
            ("knowledge", f.reference) not in claimed for f in report.knowledge_findings
        ):
            raise ArtifactInvalid()
        metrics_match = False
        for result in results:
            if result.error or not result.data or not any(s.type == "data" for s in result.sources):
                continue
            try:
                if (
                    Metrics.model_validate(result.data) == report.metrics
                    and {(s.type, s.reference) for s in result.sources if s.type == "data"}
                    <= claimed
                ):
                    metrics_match = True
            except ValidationError:
                continue
        if not metrics_match:
            raise ArtifactInvalid()
    except ValueError, TypeError:
        raise ArtifactInvalid() from None


async def finalize_artifacts(
    repository: Repository,
    provider: AgentProvider,
    run: Run,
    session_id: str,
    turn_id: str,
    response: ApplicationResponse,
) -> None:
    profile = run.config.runtime_profile
    if profile.environment_type == "none":
        return
    conversation, _ = await repository.execution_context(run.id)
    saved = await repository.get_saved_artifacts(conversation.scope, run.id)
    if saved is not None:
        if (
            run.output_mode == "report"
            and response.kind == "answer"
            and not any(a.path == "/workspace/outputs/report.json" for a in saved)
        ):
            raise ArtifactInvalid()
        return
    artifacts = await provider.list_artifacts(session_id, turn_id)
    if len(artifacts) > profile.max_artifacts:
        raise ArtifactInvalid()
    required = run.output_mode == "report" and response.kind == "answer"
    records = []
    paths = set()
    ids = set()
    report_seen = False
    for artifact in artifacts:
        if (
            artifact.session_id != session_id
            or artifact.turn_id != turn_id
            or artifact.size > profile.max_artifact_bytes
            or artifact.path in paths
            or artifact.id in ids
        ):
            raise ArtifactInvalid()
        name = safe_filename(artifact.path, artifact.media_type)
        paths.add(artifact.path)
        ids.add(artifact.id)
        payload = await provider.read_artifact(
            session_id, artifact.id, max_bytes=profile.max_artifact_bytes
        )
        if not isinstance(payload, bytes) or len(payload) != artifact.size:
            raise ArtifactInvalid()
        try:
            text = payload.decode("utf-8")
            if artifact.media_type == "application/json":
                json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except ValueError, UnicodeError:
            raise ArtifactInvalid() from None
        if required and name == "report.json":
            validate_report(payload, await repository.load_tool_results(session_id, turn_id))
            report_seen = True
        records.append(
            ArtifactRecord(
                **artifact.model_dump(exclude={"id"}),
                id=str(uuid4()),
                provider_id=artifact.id,
                scope=conversation.scope,
                conversation_id=conversation.id,
                run_id=run.id,
                sha256=hashlib.sha256(payload).hexdigest(),
            )
        )
    if required and not report_seen:
        raise ArtifactInvalid()
    await repository.save_artifacts(conversation.scope, run.id, tuple(records))
