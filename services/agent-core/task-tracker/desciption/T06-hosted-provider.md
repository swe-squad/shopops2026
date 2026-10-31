# T06 OpenAI-hosted Provider and Lifecycle

> **For agentic workers:** Use `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` when delegation is selected. Track work with checkboxes.

**Goal:** Implement actual OpenAI-hosted sessions, provisioning inspection, artifacts and bounded cleanup without duplicate provider mutations.

**Architecture:** The existing official-SDK adapter selects the conversation-pinned profile. A dedicated hosted module builds validated environment requests; OpenAI provisions compute and runs the harness.

**Tech Stack:** Python 3.14, FastAPI, SQLite, official OpenAI SDK, pytest, Docker and existing MCP transport.

**Spec:** [Managed runtime extension](../../agents_api_managed_runtime_spec.md), [main spec](../../agents_api_template_spec.md), [tracker](../task_list.md#hosted-runtime-extension-t05t08).

**Status:** Ready for integration (offline module verified; hosted live acceptance unverified). **Difficulty:** D5 — Very hard. Setup races, unknown mutation outcomes, root/child streams and cleanup errors can leave active or billable remote resources.

## Global constraints

Read the root and service AGENTS.md, the main template spec, runtime extension spec, and the tracker's **Hosted runtime extension (T05–T08)** section first. All paths below are relative to `services/agent-core/`; root workflows/templates/scripts and other services are read-only. Use Python 3.14, pinned dependencies, Ruff line length 100, one SQLite owner/worker/replica and existing API scopes. Keep default CI offline except loopback. You are not alone in the codebase: preserve other owners' changes and import shared amendments from T05 rather than copying files.

Do not copy env files between worktrees or print credentials, prompts, model output, tool data or command output in logs/evidence. Existing `none` live evidence is not hosted acceptance. Work in the assigned separate worktree and keep a private venv/DB/evidence directory. Use commits `type(agent-core): message` and preserve the workspace until the lead integrates the committed handoff. Do not merge, deploy or change another service.

## Worktree and dependencies

Use `feat/agent-core-t06-hosted-provider`, label `agent-core-t06`; Git fallback `/tmp/shopops2026-agent-core/T06`. Start code only from the published T05 runtime foundation SHA and record it. T07 can run in parallel; consume its bundle interface through a foundation double until handoff.

## File ownership

- `app/providers/openai_agents.py`, new `app/providers/hosted_runtime.py`.
- Provider-only tests: `tests/providers/test_hosted_runtime.py`, `tests/providers/test_hosted_lifecycle.py`, and existing provider wire/event tests where behavior changes.
- Provider notes in this description. Request shared dependencies, settings, models and worker changes from T05.

Do not edit T07 bundles/skills or T08 live scripts. Never implement a shell executor in the backend.

## Interfaces

Consume T05's RuntimeProfile/RuntimeBundle/ProviderEnvironment/ProviderArtifact, amended ProviderSession/Snapshot/Event/AgentProvider, and T07's `build_runtime_bundle(profile) -> RuntimeBundle`.

Produce `build_hosted_environment(profile: RuntimeProfile, bundle: RuntimeBundle) -> dict`. Extend existing `create_session(config, correlation_id, *, initial_input=None)` to dispatch by pinned profile, pass initial input once and return environment metadata. Implement async `list_artifacts(session_id, turn_id)` and bounded `read_artifact(session_id, artifact_id, *, max_bytes)` exactly as frozen by T05. Keep session/root correlation and source loading intact.

## Review focus

- A returned session with a provisioning environment is not a successful sandbox run.
- A timeout after remote creation must not trigger fallback or another create call.
- Environment/child events may omit root turn IDs; inspect saved state before terminal decisions.
- Declared artifact sizes can be wrong; enforce the limit while reading bytes.
- Delete 409/404, transport failure and unknown cleanup outcomes must be distinguished.

## Steps

- [x] **1. Verify supported SDK surface without network.** Inspect pinned SDK 3.42.0 types/resources for hosted plugins, environment status and artifacts. Ask T05 for an isolated verified dependency amendment only if necessary; record any unavailable feature explicitly.
- [x] **2. Write request tests and verify RED.** In `test_hosted_runtime.py`, assert `openai_hosted`, `small`, disabled network, approved inline skill-only plugin, initial input/correlation, multi_agent enabled with maximum two. Reject wrong digest/profile and unexpected env/package/setup fields. Assert no API key/JWT/signing secret enters the serialized request. Run `.venv/bin/pytest tests/providers/test_hosted_runtime.py -v` and confirm missing behavior fails.
- [x] **3. Implement request selection.** Implement build_hosted_environment and adapter dispatch, preserving explicit `none` compatibility and no hosted-to-none/fake fallback. Use existing SDK mutations and disabled automatic retries; do not construct a custom agent loop.
- [x] **4. Write lifecycle regressions and verify RED.** In `test_hosted_lifecycle.py`, simulate provisioning→connected, setup failure/timeout, environment expiry, child completion before root, duplicate/out-of-order command events, stream loss, and a create timeout with unknown outcome. Run `.venv/bin/pytest tests/providers/test_hosted_lifecycle.py -v`.
- [x] **5. Implement inspection/artifact/cleanup behavior.** Normalize environment state and saved activity; return only root artifacts for the owned session/turn. Read at most max_bytes with early abort. Handle known delete 409 with at most three attempts within recovery deadline, 404 as absent, and unknown results as unresolved cleanup. Preserve lifecycle IDs for T05; never equate accepted cleanup with physical sandbox destruction.
- [x] **6. Verify provider scope.** Run `.venv/bin/pytest tests/providers -v` and `make lint`; all offline provider regressions must pass without credentials. T08 later supplies real command/skill/child/artifact evidence. A live smoke is optional during module work and is never a substitute for deterministic recovery tests.
- [x] **7. Commit and hand off.** Use `feat(agent-core): add OpenAI hosted session provider`, include test results and exact SDK/contract SHA, and list unresolved lifecycle observations. Ready for integration does not mean AC16/AC20/AC21 live acceptance passed.

## Credentials and live prerequisites

OPENAI_API_KEY and OPENAI_MODEL are needed only for actual OpenAI calls. Use the existing explicit credentials-file loader or process environment; never read/copy a root env implicitly. Any optional hosted live test must require both live flags, use synthetic data and attempt cleanup in finally. Unavailable hosted account/model permissions are an explicit missing prerequisite, not permission to switch runtimes.


## Handoff record

- Actual worktree: `/tmp/shopops2026-agent-core/T06`; branch: `feat/agent-core-t06-hosted-provider`.
- Base: `428e2c7` (T05 handoff). Imported foundation: `1e45865ce1e4a3cb2b2518740b0c51b9efe2f967`; required shared lifecycle amendment: `ebd7537`. No shared files were copied from dirty worktrees.
- Result implementation commit: `dc05790` (`feat(agent-core): add OpenAI hosted session provider`). Changed-path audit is against `428e2c7`; only the two owned provider modules, provider tests and this description change, all under `services/agent-core/`.
- Python 3.14.7, official `openai==3.42.0`; no dependency amendment. Baseline provider/runtime tests: **23 passed**. Request regressions first failed on the missing hosted builder/dispatch; lifecycle regressions first failed on missing environment/artifact methods and cleanup behavior. Additional recovery regressions reproduced unsafe follow-up, metadata size/header mismatch, unconfirmed deletion and invalid-profile fallback before fixes.
- `env -u AGENT_CORE_LIVE -u AGENT_CORE_LIVE_HOSTED make ci PATH=<service>/.venv/bin:/usr/bin:/bin`: **295 passed, 1 skipped**, Ruff lint/format pass. The skipped test is the explicitly opt-in legacy live gate. Default network guards remain enabled. Elevated execution was needed for sandbox async/thread shutdown, as in T05.
- Real SDK over offline HTTP transport verifies hosted session create, environment retrieval, root artifact list/metadata/streaming content, independent artifact/session deletion and disabled automatic retries. A chunked SDK response proves oversized content stops transport consumption early and closes the response. No OpenAI request or credentials were used.
- Final scoped `.venv/bin/pytest tests/providers -q`: **72 passed**. Independent read-only review found no concrete P0/P1 in the provider delta. The reviewer's supplementary test run was interrupted and is not counted as passed; test evidence above was run by the implementer.
- `graphify update .`: completed within the service; output ignored. SQL extraction remains partial because `tree_sitter_sql` is unavailable. No shared graph, repository config or other service was modified.
- Offline AC16 request/inspection and AC20/AC21 boundary evidence only. Real hosted command/skill/subagent/egress/artifact acceptance remains **UNVERIFIED**; no deployment, push, merge or billable hosted test occurred.

### Lifecycle ruling and integration prerequisites

Create returns the known session/environment IDs, initial-input receipt and `provisioning` state
immediately. T05 atomically persists these before polling. It owns the durable 60-second setup
budget within the run deadline and cancellation/reconciliation. Waiting inside create would lose
recovery IDs if provisioning timed out. Actual connection status comes from
`client.beta.agents.environments.retrieve`, not the environment configuration in the create
response. Neither an event nor stream EOF establishes root completion. Existing T05 setup,
cancellation, restart and artifact-finalization regressions pass in full CI.

Environment expiry/disconnection/suspension is unavailable; no replacement or follow-up submit
is attempted. Unknown creation/transport outcomes raise sanitized errors without retry/fallback.
Command and subagent activity is sanitized; duplicate event IDs remain stable for T05's durable
deduplication. Artifact listing only exposes completed root-turn records; bounded reads validate
ownership, canonical path/media type, declared/actual length, UTF-8 and actual bytes received.

Cleanup independently attempts all listed artifacts and session deletion. Known session 409 gets
at most three attempts; 404 is absence. Uncertain/partial results raise ProviderOutcomeUnknown so
T05 retains cleanup_failed/session/artifact mappings. The provider's cleanup budget defaults to
60 seconds, can be reduced by constructor keyword `cleanup_timeout_seconds`, and never retries an
unknown mutation. A confirmed delete response establishes session removal/cleanup request only;
it does not establish physical sandbox destruction.

T07 must replace the fail-closed bundle stub and supply the registered digest and hosted
instructions/capabilities; the existing instructions still prohibit sandbox/delegation until its
handoff is integrated. Archive/manifest validation belongs to T07; T06 validates the returned
bundle identity/digest and closed inline-plugin SDK envelope. T05 owns final registry activation,
bundle packaging/path configuration and any reduced cleanup-budget wiring. T08 supplies hosted
live/failure acceptance. Do not activate the placeholder registry digest or report fakes/SDK wire
checks as real hosted execution. The worktree remains for integration by the lead.

Update this description only for your handoff; the runtime integration lead updates the central task table. Mark Ready for integration after module verification, not Done until required integration evidence is accepted.
