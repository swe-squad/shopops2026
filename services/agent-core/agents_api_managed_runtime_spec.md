# Managed Codex Harness and OpenAI-hosted Runtime Extension

Status: **Specified; implementation not started.** Date: 2026-10-31.

This extends the [template spec](agents_api_template_spec.md) and [basic requirements](agents_api_template_requirements.md). T01–T04 delivered the conversation/tool baseline. T05–T08 deliver the hosted runtime described here; existing baseline test results do not establish these new capabilities.

## 1. Intent, scope, and decisions

Use the **Managed Codex Harness through the OpenAI Agents API**, with an **OpenAI-hosted sandbox**, approved skills, real specialist delegation, and downloadable report artifacts. Keep application identity, authorization, durable scheduling, and internal MCP function handlers in agent-core. OpenAI runs the model/tool reasoning loop; the worker coordinates application delivery and recovery.

The existing `environment.type=none` profile already uses the managed harness. It remains a compatibility profile, not evidence of hosted execution. The new starter profile must use `openai_hosted`; an unsupported hosted feature must fail explicitly, never fall back to `none`, a fake provider, local shell execution, Agents SDK, or a custom Responses loop. [OpenAI architecture](https://developers.openai.com/api/docs/guides/agents-api/architecture)

Approaches considered:

| Approach | Tradeoff and decision |
| --- | --- |
| Keep `none` only | Preserves the baseline, but cannot satisfy workspace/code/skill acceptance |
| Add `openai_hosted` | Selected for this extension: OpenAI manages sandbox compute; internal MCP remains behind the existing bridge |
| Add `self_hosted` | Deferred: requires executor provisioning and lifecycle management beyond this template |

The selected approach follows the user's requested hosted capabilities. Limits and interfaces below are implementation design decisions, not claims that OpenAI enforces application-specific permissions.

Required: executable Python report generation, versioned skills, two specialist roles, same-session follow-up, artifact access, restart recovery, and confirmed cleanup. Deferred: arbitrary uploads/plugins, user-selected shell commands/paths, direct sandbox access to the private cluster, browser use, write actions against shops, a vector database, independent specialist credentials, and long-term memory outside a conversation.

## 2. Runtime profiles and compatibility

`APP_ENV` describes the backend deployment (`local`, `test`, `develop`, `production`). The immutable runtime profile selects the provider execution environment. Do not introduce a global environment override that silently changes existing conversations.

| Profile | Environment | Capabilities |
| --- | --- | --- |
| `conversation-v1` | `none` | Existing function/MCP conversation flow; no sandbox or delegation acceptance |
| `shopops-hosted-v1` | `openai_hosted` | Approved workspace bundle, Python execution, two specialist roles, report artifacts |

Extend `ConfigSnapshot` with `runtime_profile: RuntimeProfile | None = None`. Missing legacy fields normalize once to `conversation-v1` when reading a persisted snapshot. Do not resolve legacy rows through a mutable active profile. Store the full normalized profile in each new conversation/run snapshot.

`RuntimeProfile` is a frozen, closed model with `profile_id`, `environment_type` (`none` or `openai_hosted`), optional `bundle_id`, `bundle_version`, `bundle_sha256`, optional `container_size` (`small` only in this milestone), `network_access` (`disabled`), `multi_agent_enabled`, `max_concurrent_subagents`, `setup_timeout_seconds`, `max_artifacts`, and `max_artifact_bytes`.

For `shopops-hosted-v1`, require a registered bundle/digest, `multi_agent_enabled=true`, `max_concurrent_subagents=2`, setup timeout `60` seconds, at most `2` artifacts per run, and at most `1048576` bytes per artifact. For `conversation-v1`, sandbox/bundle fields are absent and delegation is disabled. Reject unknown profiles, inconsistent combinations, or invalid bundle hashes before provider mutations. Profile selection is administrative through a new registry revision, not request-body parameters.

Keep old revisions loadable and sessions unmigrated. A dev registry must use internal cluster MCP URLs throughout; carrying local loopback revisions into a develop registry is already rejected by the existing allowlist validation. The live model still comes from `OPENAI_MODEL` and must match the registered model; there is no new hardcoded model default.

## 3. Provider request and execution boundaries

The provider continues to use `client.beta.agents.sessions`. Its hosted create request includes initial input and correlation metadata, configured function tools, `agent.multi_agent={enabled: true, max_concurrent_subagents: 2}`, and the environment fragment:

```json
{
  "type": "openai_hosted",
  "container_size": "small",
  "network": {"access": "disabled"}
}
```

Add the registered bundle through the documented `environment.plugins` inline ZIP mechanism. The skill-only plugin contains no MCP connection or credentials. Packages use the sandbox's existing Python standard library; no runtime package downloads, third-party installers, arbitrary setup commands, or inherited environment variables are needed. [Hosted configuration](https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted), [plugin packaging](https://developers.openai.com/api/docs/guides/agents-api/tools/plugins)

A create response is not proof that setup succeeded. Inspect the returned environment ID and wait for `connected` within the setup deadline and remaining application run deadline. Treat failed setup as `environment_failed`; a known setup deadline as `environment_timeout`; uncertain mutation outcomes retain the existing reconciliation/blocking behavior. Persist session mapping and initial-input receipt together, as in the baseline.

The existing MCP functions run in the backend. No `srv-captain--...` endpoint is supplied as a sandbox-accessible MCP connection. Keep `OPENAI_API_KEY`, backend env files, SQLite, signing keys, JWTs, and MCP credentials outside the sandbox/plugin. Sandbox isolation is per conversation/session; specialists in the same session share one workspace and are not separate security principals.

## 4. Workspace bundle and actual specialist execution

Create a service-local, versioned skill-only plugin:

```text
runtime-bundles/shopops-hosted-v1/
  manifest.json
  shopops-analysis/
    .codex-plugin/plugin.json
    skills/returns-analysis/SKILL.md
    skills/returns-analysis/scripts/summarize_returns.py
    skills/knowledge-review/SKILL.md
    references/specialists/data-analyst.md
    references/specialists/knowledge-analyst.md
```

`manifest.json` records bundle/version, sorted file names and SHA-256 digests; its aggregate digest is computed over the sorted path/digest pairs (excluding manifest.json itself). Reject symlinks, archive traversal, absolute archive entries, duplicate entries, unregistered files, mismatched plugin metadata, and bundles exceeding `262144` uncompressed bytes. Generate ZIPs deterministically, without timestamps or other machine-specific content. Upload only this registered plugin tree. Users cannot choose archives, local paths, skill URLs, or extra files.

The harness discovers the registered plugin's skills. A live test must prove the agent reads the skill and runs its bundled script; placing instructions in the main prompt alone does not pass skill acceptance. Skills can read approved inputs and write outputs in their sandbox; they cannot grant permissions. [Agents API skills](https://developers.openai.com/api/docs/guides/tools-skills)

**Provider constraint:** subagents currently do not support function tools. The root orchestrator therefore obtains metrics and knowledge through the authorized backend bridge first. It passes bounded validated JSON, excerpts, and original source references to two harness-created specialists: `data-analyst` computes/interprets the return metrics; `knowledge-analyst` reviews the supplied policy evidence. Missing information goes back to the root for another authorized retrieval. Do not give specialists a fictional function-tool proxy. [Multi-agent contract](https://developers.openai.com/api/docs/guides/agents-api/multi-agent)

For the reporting workflow, the root invokes the bundled Python script on this data and asks specialists for independent analysis; the root combines their results into a Vietnamese response and `/workspace/outputs/report.json`. Delegation uses the harness's built-in create/message/wait tools, not a Python-side agent loop. Role labels are instructions backed by repository-owned reference files, not separately configured API agent types or per-role access controls. Use separate subdirectories for scratch work. The root is the sole writer of the canonical report. Enabling delegation does not require two children on every message: clarification, cannot_answer and simple text-only questions may finish without delegation; the compound report acceptance scenario must demonstrate both specialists.

Verify cited business sources against successful stored ToolResults for the same session and root turn. A skill, generated file, or specialist assertion does not create new business evidence. The final application response keeps the existing source schema.

## 5. Persistence and shared contracts

T05 owns freezing the following proposed boundary before other owners change shared code. Keep implementation signatures and fakes synchronized in a small foundation commit.

| Boundary | Required amendment |
| --- | --- |
| `app/contracts/runtime.py` | `RuntimeProfile`, `RuntimeBundle`, `ProviderEnvironment`, `ProviderArtifact`, `ArtifactRecord` frozen models |
| `ConfigSnapshot` | Optional legacy-compatible `runtime_profile` with immutable normalization |
| `Run` and message submission schema | `output_mode: Literal["text", "report"] = "text"`; persist in the run and include it in the idempotency request hash; legacy runs normalize to text |
| `ProviderSession`, `ProviderSnapshot` | Optional `environment: ProviderEnvironment`; preserve existing IDs, initial-input receipt and root correlation |
| `ProviderEvent` | Nullable `turn_id`; add sanitized environment/subagent/command status kinds. Events without established root identity cannot complete a run |
| `AgentProvider` | `async list_artifacts(session_id: str, turn_id: str) -> tuple[ProviderArtifact, ...]`; `async read_artifact(session_id: str, artifact_id: str, *, max_bytes: int) -> bytes` |
| Bundle builder | `build_runtime_bundle(profile: RuntimeProfile) -> RuntimeBundle` in `app/agents/runtime_bundle.py`; returns verified inline plugin payload and bundle digest, without network calls |
| Hosted request builder | `build_hosted_environment(profile: RuntimeProfile, bundle: RuntimeBundle) -> dict` in `app/providers/hosted_runtime.py`; returns only approved SDK environment fields |
| Repository | `save_runtime(scope, conversation_id, environment)`, `save_artifacts(scope, run_id, artifacts)`, `list_artifacts(scope, run_id, after, limit)`, `get_artifact(scope, artifact_id)`; all async and scoped |

Model details: `ProviderEnvironment` contains provider environment `id`, state (`provisioning`, `connected`, `failed`, `unavailable`), and sanitized error; `RuntimeBundle` contains bundle ID/version/digest and inline plugin payload; `ProviderArtifact` contains provider ID, session ID, turn ID, path, declared size and media type; `ArtifactRecord` adds local UUID, full Scope, conversation/run IDs, verified size/digest and availability. Never expose plugin payloads through API or logs. T05 publishes exact repository argument/return types in `contracts/managed-runtime.md` at its foundation gate.

Add migration `app/storage/migrations/002.sql` for runtime mappings, run output_mode and artifact metadata, unique on conversation/environment ownership and provider artifact/session/turn. Preserve existing rows and the single SQLite owner lock. No destructive migration or automatic session replacement. Store provider IDs for recovery, not public lookup. Artifact bytes remain in the provider and are fetched with limits; no new local file store is needed.

## 6. Artifacts and application API

Extend message submission with optional `output_mode`, a closed enum `text|report` defaulting to `text`. It selects a result format, not a runtime, skill, path or permission. Reject `report` for the legacy conversation profile with `422 invalid_input`. Include output_mode in replay/conflict detection. Clients that omit it retain existing behavior.

Expose only artifacts returned by the provider for the owned session and completed **root** turn, with canonical paths under `/workspace/outputs/`. Reject traversal, unknown media types, excess count, and oversize content. This milestone supports UTF-8 JSON and Markdown only. Require `report.json` only for a run submitted with output_mode=report that finishes with response.kind=answer. A clarification or cannot_answer remains a completed response without a report, including when report was requested; it must not imply report generation succeeded. Text-mode turns may complete without artifacts or metrics retrieval. The closed report JSON has exactly `schema_version` (literal `1`), `metrics` (the existing get_return_metrics data schema), `knowledge_findings` (at most 10 objects with `reference` and a 1–2000-character `finding`), and `sources` (the existing Source array). T05 freezes this as `contracts/runtime-report.schema.json`; T07 scripts and T08 assertions consume it. Require a nonempty data source and knowledge source, match metrics/knowledge references to successful stored ToolResults for this session/root turn, and reject unknown keys. Verify structure, numeric values and sources before publishing it; generated report text is untrusted data.

List and bounded-read artifacts at root completion; persist validated metadata and digest before completing the application run. Replays reuse saved metadata. A required report missing or invalid fails the run with `artifact_invalid`; it cannot masquerade as a successful report. For text-mode/clarification/cannot_answer turns, do not demand the report schema or fabricate data to fill it. Download validates size/digest again and does not execute or render generated files.

| Route (prefix `/api/v1`) | Contract |
| --- | --- |
| `GET /runs/{run_id}/artifacts?after=...&limit=...` | `history:read`; existing scoped opaque pagination, 1–100/default 50; local artifact IDs, run ID, filename, media type, size, digest, availability |
| `GET /artifacts/{artifact_id}/content` | `history:read`; resolve local scoped record before provider access; attachment response, fixed safe filename, no provider URL redirect |

Both routes enforce tenant/shop/owner membership and return `404` for a foreign ID. No API accepts provider session IDs or arbitrary remote/local paths. A known artifact no longer retrievable returns `410 artifact_unavailable`; transient provider I/O returns sanitized `503`; an invalid payload returns `502 artifact_invalid`. Artifact failure does not rewrite completed conversation history.

Published artifacts outlive sandbox expiry; workspace files are not durable application storage. Correlate artifacts by session, turn, and path rather than guessing the latest file. [Artifact API and lifetime](https://developers.openai.com/api/docs/guides/agents-api/environments/files)

## 7. Recovery, resource lifecycle, and limits

Retain one active application run per conversation. Root-turn saved state remains authoritative; a child completion, command exit, environment connection, or closed stream cannot finish the root run. Record only sanitized activity/status, with provider event deduplication. Never expose command text, stdout/stderr, scratch files, raw inter-agent messages, or hidden reasoning in the client event feed.

Use existing application states: setup remains `running` with `environment.provisioning` status; uncertain provider mutations use `reconciling`. The default run deadline remains `180` seconds from enqueue, including setup, specialists, tools and artifact validation. Setup has its own upper bound of `60` seconds within that deadline. Existing MCP limits remain `15` seconds per call, `8` backend tool calls and `4` concurrent runs. These backend limits are not a claim to cap every harness-internal command or model token. No monetary spend cap is claimed.

On backend restart, inspect the saved session/environment and continue reconciliation without another create or duplicate input. A missing/expired workspace must not be replaced silently. Fail an active affected run with `environment_unavailable`; preserve known published artifacts and require a new conversation for further sandbox work. Keep unknown outcomes blocked under the baseline policy. Do not implement keep-alive or compaction logic to replace the managed harness.

On timeout/cancellation, request cancellation and establish root termination before unlocking. On conversation deletion, independently attempt removal of registered artifacts and then request hosted sandbox cleanup through session deletion; one artifact failure must not prevent the session cleanup attempt. A known delete `409` can be retried at most three times within the existing recovery deadline; transient/unknown outcomes are recorded as cleanup pending/failed and retain recovery IDs. Session `404` is idempotent absence. Do not mark physical sandbox destruction confirmed merely because session deletion was accepted; record confirmed session removal and cleanup request separately. Stream closure is never teardown.

## 8. Configuration, delivery, and credentials

All code, docs, bundles, fixtures and scripts stay under `services/agent-core/`. Reuse Python 3.14, FastAPI, SQLite, pinned `openai==3.42.0` unless the foundation owner verifies and coordinates a necessary upgrade, existing Docker/CI, and one service/worker/replica. Add only the proposed non-secret `RUNTIME_BUNDLE_PATH` setting (default `runtime-bundles`), documented in `.env.example` and README when implemented. Runtime selection, bundle version/digest and limits belong in registry revisions. This specification alone adds no runtime env variable.

Backend secrets stay in CapRover App Configs/operator process. Hosted smoke can use the existing explicit `--credentials-file` loader, which reads only key/model from an ignored file and never copies the root env. T06/T08 need credentials only for explicit live calls; T05/T07 and default CI need none. Check the installed SDK's session, environment, plugin and artifact surfaces before coding; unavailable account support is an explicit unverified/blocked live prerequisite, not an offline pass.

Future test opt-in: require both `AGENT_CORE_LIVE=1` and `AGENT_CORE_LIVE_HOSTED=1` for hosted tests. They must be skipped unless both flags are explicit, including when only the legacy live gate is enabled. The implementation will document `python -m scripts.demo_live_hosted --live --hosted --credentials-file <ignored-file> --evidence .evidence/live-hosted.json`; this command does not exist yet. Run a bounded synthetic scenario and record model/runtime/bundle digest, completed root turns, actual child IDs/command items, artifact validation and cleanup status. Do not publish content or credentials in evidence. A new sandbox run is billable model/container work; this documentation update executes none.

## 9. Acceptance and evidence

All AC01–AC14 remain required regressions. New criteria are **Not verified** until T05–T08 implementation and recorded evidence exist.

| ID | Requirement | Evidence required |
| --- | --- | --- |
| AC15 | Pin runtime and migrate legacy snapshots | Legacy sessions stay `none`; new hosted revision stays pinned after activation/restart; invalid combinations rejected before I/O |
| AC16 | Real hosted execution | Provider confirms `openai_hosted`, environment ID/connected status, successful saved Python command item, correct report numeric values |
| AC17 | Real skill loading | Version/digest matches registry; saved execution reads approved SKILL.md and executes its bundled script; changed/unapproved bundles fail offline validation |
| AC18 | Harness specialist delegation | At least two actual distinct subagent IDs/turns, expected specialist results, root synthesis; children cannot finish the application run or fabricate MCP evidence |
| AC19 | Scoped artifact delivery | Report-mode answers require a valid root report; text/clarification/cannot_answer preserve baseline semantics; correct report downloaded and validated; cross-user/shop/tenant, traversal, oversize and digest mismatch rejected; expired artifact distinguished |
| AC20 | Setup/restart/cancellation/cleanup failures | Offline failure injection for setup failure/timeout, stream loss, restart with known/unknown session, expiry, delete 409/404, cleanup retry/recovery IDs |
| AC21 | Sandbox and credential boundaries | Offline checks validate disabled-network requests and secret exclusion; hosted live command items establish a harmless egress-denial probe and absent backend-secret names without printing values; only synthetic inputs are used |
| AC22 | End-to-end hosted acceptance | Real skills + Python + two specialists + MCP data/knowledge + same-session follow-up + artifact download + separate-conversation isolation + confirmed session removal/cleanup request; default CI remains offline |

Live acceptance cannot be satisfied by a hardcoded artifact, a local subprocess, a fake provider, prompt-only skill text, or merely setting `multi_agent.enabled`. If saved items do not establish a required action, report it unverified. Existing AC13 evidence for `none` remains valid only for the baseline.

## 10. Implementation order

[T05](task-tracker/desciption/T05-runtime-foundation.md) first publishes the shared runtime foundation. [T06](task-tracker/desciption/T06-hosted-provider.md) and [T07](task-tracker/desciption/T07-skills-specialists.md) then implement independent provider/bundle modules in separate worktrees. [T08](task-tracker/desciption/T08-hosted-acceptance.md) can prepare acceptance fixtures after the foundation, but final verification waits for both module handoffs and T05 application wiring. No new task has started, no foundation SHA is published for this extension, and no hosted live result is claimed.
