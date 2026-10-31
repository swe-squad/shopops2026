# Managed runtime foundation (T05)

All models are frozen and reject unknown keys. Missing ConfigSnapshot.runtime_profile normalizes
independently of the registry to RuntimeProfile() (conversation-v1 / none). Run.output_mode defaults
to text. Existing snapshots and sessions never inherit an active hosted profile.

`app/contracts/runtime.py` defines RuntimeProfile, RuntimeBundle, ProviderEnvironment,
ProviderArtifact, ArtifactRecord. ArtifactRecord.id is a local UUID; provider_id is private.
RuntimeBundle.inline_plugin is private and excluded from serialization. Network access is disabled.
Only shopops-hosted-v1 with a pinned bundle ID/version/SHA256, small container, two subagents and
60-second setup is accepted. Limits are two artifacts and 1048576 bytes per file or stricter.

All Repository methods below are async. Exact types are exported by app/contracts/repository.py:

```python
save_runtime(scope: Scope, conversation_id: str, environment: ProviderEnvironment) -> None
get_runtime(scope: Scope, conversation_id: str) -> ProviderEnvironment | None
save_artifacts(scope: Scope, run_id: str, artifacts: tuple[ArtifactRecord, ...]) -> None
list_artifacts(scope: Scope, run_id: str, after: str | None = None,
               limit: int = 50) -> Page[ArtifactRecord]
get_artifact(scope: Scope, artifact_id: str) -> ArtifactRecord
load_tool_results(session_id: str, turn_id: str) -> tuple[ToolResult, ...]
```

Runtime mappings have one immutable environment owner. Artifact writes validate conversation,
scope, session and root turn in one transaction; replay verifies unchanged metadata. Metadata is
invisible until the root run completes. Foreign IDs resolve to NotFound before provider I/O.
Only internal source validation uses load_tool_results; it is not a public endpoint.

AgentProvider adds async list_artifacts(session_id, turn_id) -> tuple[ProviderArtifact, ...]
and read_artifact(session_id, artifact_id, *, max_bytes: int) -> bytes. Providers must enforce
max_bytes during transport, before accumulating an oversized body. ArtifactUnavailable represents
known remote absence, ArtifactInvalid invalid bytes/metadata, ArtifactTransient transient I/O.
Session and snapshot carry optional ProviderEnvironment. Nullable event.turn_id and sanitized
activity kinds are hints only; only an inspected, correlated root can finalize a run. No command,
child response, stream closure or environment event is authoritative root completion.

The report schema is contracts/runtime-report.schema.json, generated from RuntimeReport. It
reuses Metrics validation, including numeric rates, and existing Source. Worker validation must
also match metrics and references to successful ToolResults from this session and root turn.
Report mode requires report.json only for answer. Clarification/cannot_answer need no report.

T06 owns app/providers/hosted_runtime.py after foundation import; T07 owns
app/agents/runtime_bundle.py after import. These foundation stubs fail explicitly and perform no
network, shell execution or fallback. Builders use signatures in the extension spec. No provider
or bundle handoff is implied by their presence. Consumers must record the imported foundation SHA.

Cleanup preserves the existing deleting/cleanup_failed conversation with provider session IDs on
failure. Do not replace sessions or clear recovery mappings on uncertain remote outcomes.

SDK audit (offline, 3.42.0): sessions.create accepts EnvironmentParamOpenAIHosted with
plugins/disabled network/small container. sessions.artifacts exposes list/retrieve/content/delete;
T06 must filter list results to the authoritative root turn and bound streaming reads. No SDK
upgrade is needed for these surfaces. Account capability/live behavior remains unverified.

Recovery amendment: `Run.artifacts_finalized` is persisted atomically with artifact metadata,
including an empty validated set. Internal async `get_saved_artifacts(scope: Scope, run_id: str)
-> tuple[ArtifactRecord, ...] | None` distinguishes not-yet-validated from validated-empty.
Recovery reuses this set without remote downloads; public listing still requires completed root
state. No failed download rewrites completed history. `enqueue_message` adds keyword-only
`output_mode: Literal["text", "report"] = "text"`; replay compares both digest and stored mode.
Hosted execution passes an application output-format directive on each provider input; baseline
provider inputs remain unchanged. Source validation requires the cited data reference to identify
the ToolResult whose metrics match, not another result within the same root turn.

`Run.runtime_setup_started_at` is persisted when marking session creation before provider I/O;
setup uses that timestamp with the remaining application deadline, so queue delay does not
consume the setup budget. Unknown mutation outcomes retain the existing reconciliation policy.

Integration amendment: `build_runtime_bundle(profile, *, bundle_root: Path | None = None)` keeps
its original one-argument behavior and accepts a validated operator directory when configured.
The configured live provider receives the same directory used by startup validation. The image
ships the registered skill-only bundle; no secret or arbitrary user path enters its payload.
First connection is validated against the durable setup deadline even if it arrives connected;
known session/receipt/environment IDs survive failure for cleanup. An established connection is
not subject to another setup deadline on follow-up work.
