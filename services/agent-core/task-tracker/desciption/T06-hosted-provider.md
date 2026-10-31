# T06 OpenAI-hosted Provider and Lifecycle

> **For agentic workers:** Use `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` when delegation is selected. Track work with checkboxes.

**Goal:** Implement actual OpenAI-hosted sessions, provisioning inspection, artifacts and bounded cleanup without duplicate provider mutations.

**Architecture:** The existing official-SDK adapter selects the conversation-pinned profile. A dedicated hosted module builds validated environment requests; OpenAI provisions compute and runs the harness.

**Tech Stack:** Python 3.14, FastAPI, SQLite, official OpenAI SDK, pytest, Docker and existing MCP transport.

**Spec:** [Managed runtime extension](../../agents_api_managed_runtime_spec.md), [main spec](../../agents_api_template_spec.md), [tracker](../task_list.md#hosted-runtime-extension-t05t08).

**Status:** Not started. **Difficulty:** D5 — Very hard. Setup races, unknown mutation outcomes, root/child streams and cleanup errors can leave active or billable remote resources.

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

- [ ] **1. Verify supported SDK surface without network.** Inspect pinned SDK 3.42.0 types/resources for hosted plugins, environment status and artifacts. Ask T05 for an isolated verified dependency amendment only if necessary; record any unavailable feature explicitly.
- [ ] **2. Write request tests and verify RED.** In `test_hosted_runtime.py`, assert `openai_hosted`, `small`, disabled network, approved inline skill-only plugin, initial input/correlation, multi_agent enabled with maximum two. Reject wrong digest/profile and unexpected env/package/setup fields. Assert no API key/JWT/signing secret enters the serialized request. Run `.venv/bin/pytest tests/providers/test_hosted_runtime.py -v` and confirm missing behavior fails.
- [ ] **3. Implement request selection.** Implement build_hosted_environment and adapter dispatch, preserving explicit `none` compatibility and no hosted-to-none/fake fallback. Use existing SDK mutations and disabled automatic retries; do not construct a custom agent loop.
- [ ] **4. Write lifecycle regressions and verify RED.** In `test_hosted_lifecycle.py`, simulate provisioning→connected, setup failure/timeout, environment expiry, child completion before root, duplicate/out-of-order command events, stream loss, and a create timeout with unknown outcome. Run `.venv/bin/pytest tests/providers/test_hosted_lifecycle.py -v`.
- [ ] **5. Implement inspection/artifact/cleanup behavior.** Normalize environment state and saved activity; return only root artifacts for the owned session/turn. Read at most max_bytes with early abort. Handle known delete 409 with at most three attempts within recovery deadline, 404 as absent, and unknown results as unresolved cleanup. Preserve lifecycle IDs for T05; never equate accepted cleanup with physical sandbox destruction.
- [ ] **6. Verify provider scope.** Run `.venv/bin/pytest tests/providers -v` and `make lint`; all offline provider regressions must pass without credentials. T08 later supplies real command/skill/child/artifact evidence. A live smoke is optional during module work and is never a substitute for deterministic recovery tests.
- [ ] **7. Commit and hand off.** Use `feat(agent-core): add OpenAI hosted session provider`, include test results and exact SDK/contract SHA, and list unresolved lifecycle observations. Ready for integration does not mean AC16/AC20/AC21 live acceptance passed.

## Credentials and live prerequisites

OPENAI_API_KEY and OPENAI_MODEL are needed only for actual OpenAI calls. Use the existing explicit credentials-file loader or process environment; never read/copy a root env implicitly. Any optional hosted live test must require both live flags, use synthetic data and attempt cleanup in finally. Unavailable hosted account/model permissions are an explicit missing prerequisite, not permission to switch runtimes.


## Handoff record

- Actual worktree / branch: not recorded.
- Base SHA / imported T05 foundation SHA: not recorded.
- Result commit SHA / changed-path audit: not recorded.
- Scoped test commands/results / relevant acceptance IDs: not recorded.
- Live evidence or exact missing prerequisite / unresolved integration issues: not recorded.

Update this description only for your handoff; the runtime integration lead updates the central task table. Mark Ready for integration after module verification, not Done until required integration evidence is accepted.
