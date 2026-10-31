# T03 Agent Provider and Instructions Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Track progress with checkboxes.

**Goal:** Supply interchangeable fake/live Agents API adapters and grounded Vietnamese-response instructions without coupling provider code to worker or storage internals.

**Architecture:** A shared provider interface normalizes sessions, turns, pending actions, events and results. T01 owns durable scheduling/recovery; this adapter exposes enough provider state to reconcile safely.

**Tech Stack:** Python, official `openai` SDK, async transport interfaces, pytest with mocked transport.

**Spec:** [Agent Core Template Spec](../../agents_api_template_spec.md), sections 1–2, 4, 6–8 and 11.

**Tracker and global constraints:** [Task list](../task_list.md). Owner: agent/provider developer. Status: **Blocked** (live session creation contract; offline module available).

**Difficulty:** D4 — Hard. Provider session/turn semantics, async stream recovery, pending actions, SDK compatibility and grounded output normalization must agree with the worker contract. Live access can block acceptance even when offline adapter tests pass.

**OpenAI credentials:** The live adapter smoke test and demo require `OPENAI_API_KEY` and `OPENAI_MODEL` in the running process. Offline fake-provider and mocked-transport tests require neither. The original checkout's root `.env` declares the key name, but is not automatically available or loaded in this worktree; its validity and permissions are unverified. Supply variables through the operator's environment/secret manager, or an ignored worktree-local service `.env` explicitly loaded by a documented loader. Never print, copy the entire root `.env`, or commit credentials. See [OpenAI API key by task](../task_list.md#openai-api-key-by-task).

## Repository scope and worktree

Read the tracker's **Required repository workflow** and **Separate worktrees** sections before coding. Use the existing Python 3.14 FastAPI service layout, service-local test environment and pinned dependency conventions. All source, fixtures, tests and scripts stay inside `services/agent-core/`; do not introduce a root SDK package, workflow or shared dependency file.

Use branch `feat/agent-core-t03-provider` in the dedicated `agent-core-t03` worktree; Git fallback: `/tmp/shopops2026-agent-core/T03`. Start from T01's published foundation commit SHA and work from `<worktree>/services/agent-core/`. Keep live credentials in this worktree's ignored runtime configuration; never copy the root `.env` or another owner's secrets. Request SDK/dependency changes from T01 as isolated commits.

## File ownership

Paths are relative to `services/agent-core/`. You are not alone in the codebase: preserve other owners' changes. T01 owns shared dependencies/types; submit SDK version requests with compatibility evidence.

| Create or maintain | Responsibility |
| --- | --- |
| `app/providers/{fake,openai_agents,normalization}.py` | Provider adapters, event/error normalization and application output validation |
| `app/agents/{instructions,capabilities}.py` | Orchestrator instructions, template selection and delegation extension point |
| `fixtures/provider/` | Synthetic session/events, pending calls, failures and replay fixtures |
| `tests/providers/`, `tests/agents/` | Shared provider conformance tests and output/grounding tests |
| `scripts/demo_live.py`, `tests/live/test_agents_api.py` | Explicitly opt-in live smoke and cleanup |

Do not own run persistence, worker state transitions, MCP transport or API routes. Do not introduce specialist execution, arbitrary skill loading or sandbox access into the MVP.

## Interfaces and dependencies

Consume T01's `AgentProvider`, `ProviderSession`, `ProviderSnapshot`, `ProviderEvent`, `PendingToolCall`, `ToolDefinition`, `ToolResult`, `ConfigSnapshot`, and `ApplicationResponse`.

The gate must define exact signatures for `create_session`, `inspect_session`, `submit_input`, `stream_events`, `submit_tool_result`, `list_items`, `cancel_turn`, and `delete_session`. Both implementations pass the same conformance suite. Streams expose explicit subscription readiness so T01 can subscribe before submitting input.

Consume T04 tool definitions without importing its MCP client. Pending calls must carry session/turn/call identity; root-turn completion must be distinguishable from subagent completion. Output normalization accepts the run's persisted source references supplied by T01 and rejects unknown references.

## Implementation checklist

- [x] **Worktree baseline:** Record the foundation SHA, read service `AGENTS.md`, run `make install`, the available baseline tests and `make lint` in this worktree. Keep offline provider tests separate from opt-in live tests.
- [ ] **Prerequisite check:** Before implementing the live adapter, verify the official Agents API docs and installed SDK surface. Request a pinned SDK version exposing `beta.agents`; preserve `OPENAI_MODEL` configuration and distinguish unavailable credentials/access from code defects.
- [ ] **Conformance tests first:** Create `tests/providers/test_contract.py` covering lazy session creation, reuse, isolated sessions, pending function calls, tool-result submission, inspection, item retrieval and cancellation. Run against the fake implementation and a mocked live transport.
- [x] **Fake provider:** Implement deterministic multi-turn scenarios: returns metrics, knowledge question, clarification, tool failure, duplicate event and interrupted stream. Invoke pending tool calls through the same protocol boundary as live execution; do not bypass T04 or return hardcoded successful integration evidence.
- [ ] **Live adapter:** Implement async session/input/event operations using the official SDK and no application credentials in agent context. Normalize transport errors with an explicit unknown-outcome marker; do not retry mutations or create replacement sessions implicitly.
- [x] **Event/recovery tests:** Add `test_stream_loss_is_not_completion`, `test_subagent_completion_does_not_complete_root`, `test_pending_actions_require_current_provider_state`, and `test_timeout_submit_is_uncertain` in `tests/providers/test_events.py`. Expose provider IDs/state for T01 reconciliation without mutating the application DB.
- [x] **Instructions and output tests:** Add `tests/agents/test_grounding.py` for Vietnamese answer instructions, missing-SKU/date clarification, no invented zero values, and rejection of source IDs absent from persisted tool results. Implement application response kinds `answer`, `clarification`, `cannot_answer`; do not assert exact model prose.
- [x] **Capability profile:** Publish only approved tools from the pinned config; provide a delegation extension point without launching specialists. Do not allow prompts to override identity, MCP URLs, credentials or tool permissions.
- [ ] **Live smoke:** Provide an explicit opt-in script/test using synthetic fixture data. It must create a real session, finish one MCP-backed function call through T01/T04, ask a follow-up in the same session and attempt scoped cleanup even after failure. Capture sanitized evidence, not prompts or secret values in logs.
- [ ] **Handoff:** Give T01 working fake/live factories, conformance fixtures, event mappings, uncertainty semantics, and test results. If credentials are missing, mark live smoke unverified; continue offline adapter verification.

## Verification and completion

After T01 scaffolding, run from `services/agent-core/`:

```bash
.venv/bin/pytest tests/providers tests/agents -v
```

Expected: both adapters satisfy the same offline contract via fake/mocked transports; no real OpenAI calls occur. Live tests are excluded from default `make ci` and require explicit credentials plus integrated T01/T04. Record the exact opt-in command and outcome in the handoff; SDK mocks alone do not satisfy AC13.

Primary criteria: AC02 and AC13; support AC04, AC07–AC09 and AC14. Module handoff may be **Ready for integration** with live acceptance explicitly unverified. Completion evidence must distinguish offline conformance from actual Agents API execution. Use commits such as `feat(agent-core): add Agents API provider adapter`.

## Handoff record

Record the actual worktree path, branch, foundation SHA, result commit SHA, changed paths, offline test results and live smoke status/blockers here. Confirm all task changes are under `services/agent-core/`. T01 updates the central tracker and integrates committed changes; preserve the worktree until integrated or otherwise safely retained.


### T03 handoff — 2026-10-31

- Worktree: `/tmp/shopops2026-agent-core/T03`; service working directory:
  `/tmp/shopops2026-agent-core/T03/services/agent-core`.
- Branch: `feat/agent-core-t03-provider`; integration destination: `feat/agent-core-template`.
- Foundation: `9ce01a24f19acdfc4e5803faec1e1a3fa1fd678f`.
- Implementation result: `9ec26a0` (`feat(agent-core): add offline provider adapters and grounding checks`).
  The subsequent documentation commit records this handoff; retain both commits.
- Changed paths: `app/providers/{fake,normalization,openai_agents}.py`,
  `app/agents/{instructions,capabilities}.py`, `fixtures/provider/scenarios.json`,
  `tests/providers/`, `tests/agents/`, `tests/live/`, `scripts/demo_live.py`, and this task description.
  All paths are under `services/agent-core/`. Shared contracts/dependencies/wiring and central tracker
  remain owned by T01. No merge/push/deployment was performed.

#### Verified offline evidence

- `make install`: installed foundation dependencies in this worktree's own `.venv`.
  The shell initially selected Python 3.13; the environment was corrected to Python **3.14.7**.
  Use Python 3.14 first in PATH when invoking template Makefile targets (including `make install`).
- Final CI: `PATH="$PWD/.evidence/bin:$PATH" make ci` → **27 passed, 1 skipped**, lint and format clean.
  `.evidence/bin/python3` is a local ignored symlink to the installed Python 3.14 executable.
- `.venv/bin/pytest tests/providers tests/agents -q` → **24 passed**, including the optional SDK
  wire compatibility test with the locally installed `openai==3.42.0` and `httpx2` MockTransport.
  Without the requested SDK pin, that optional compatibility test skips; core adapter tests still run.
- `graphify update .` refreshed the ignored service-local AST graph.
- Tests cover isolated sessions, reuse/follow-up, pending calls, structured data/knowledge responses,
  errors, cancellation, duplicate events, interrupted streams, stale required actions, changed tool
  payload rejection, unknown mutation outcome, commentary exclusion, historical invalid output,
  forged source references, malformed output and restricted tool selection.
- Fresh review identified missing await on the real SDK stream boundary, fake output dependence on
  an undocumented summary field, and historical output validation blocking new submissions.
  All three were fixed with observed failing-then-passing regression tests; full CI is green.

#### Factories and recovery contract

- `FakeProvider(scenarios=...)`: construct once and inject as `AgentProvider`; creating the object
  performs no network work. Supply `Scenario` records from the synthetic JSON fixture as needed.
  Defaults ask for clarification; no fabricated metrics or MCP execution evidence is produced.
  Successful tool data is displayed as a synthetic Vietnamese response with original source pairs.
  It does not interpret T04 data as proven AC03 calculation evidence.
- `OpenAIAgentsProvider(client, source_loader=None)` / `build_live_provider(source_loader=None)`:
  async official SDK session operations for existing sessions. Factory requires runtime
  `OPENAI_API_KEY` and nonempty `OPENAI_MODEL`, and disables SDK automatic retries.
  No network or SDK import occurs at module import. Session creation is deliberately gated below.
- `source_loader(session_id, turn_id)` must asynchronously return the run's persisted successful
  `Source` records from T01; do not derive this allowlist from model output or session history.
  With no loader, cited outputs are rejected. T01 still validates before committing assistant history.
- Enter `stream_events`, then await `wait_ready` before submission. Real SDK stream call is awaited.
  Root `turn.created`/`turn.in_progress` map to status; terminal turn events preserve `subagent_id`.
  Requires-action events derive identity from nested `session.required_actions`; their hints have
  `is_root=False` because action payloads do not prove root identity. Inspect current root state
  before executing any pending call. EOF has no completion meaning.
- Unknown transport/SDK mutation outcomes raise sanitized `ProviderOutcomeUnknown`; no automatic
  retry, replacement session, or implicit resubmission. Tool result replay requires the exact current
  required action and uses stable `tool:<turn_id>:<call_id>` idempotency keys. T01 must retain the
  immutable call/result durably; adapter caches are optimizations, not restart persistence.
- SDK turn records do not expose input run correlation. Correlation is known locally only after a
  confirmed new root ID. After uncertain submission/restart, `input_run_id` may be absent: T01 must
  reconcile using its durable root ID or block at recovery deadline, never guess a mapping.
- Instructions support `shopops`; select only pinned read-only tools from the approved four-tool
  registry. `delegation_targets` is empty in v1. T01 must wire these builders after the contract fix.

#### Explicit live blockers / T01 requests

1. Publish a coordinated contract amendment for **atomic session creation with initial user input**,
   run ID and explicit uncertain-outcome handling. Official session documentation says
   `environment.type="none"` requires initial input, while foundation v1
   `create_session(config, correlation_id)` cannot supply it. User explicitly chose to record this
   blocker and request T01's change; do not start a hosted sandbox to bypass it. Current live
   `create_session` raises `ConfigurationConflict` before any remote mutation.
2. T01 owns requirements: request **`openai==3.42.0`** as a separate dependency commit.
   Locally verified on Python 3.14.7: `AsyncOpenAI.beta.agents.sessions`, async retrieve/delete,
   events.create/stream, turns.list and items.list. Include its runtime HTTP dependency in the
   deployment image through this pin. No shared dependency file was edited by T03.
3. Integrate T01 worker/repositories and T04 real loopback MCP bridge, source loader and scoped
   administrative cleanup. Then implement/run full AC13: real creation, MCP function result,
   follow-up on the same session, cleanup attempted in finally even on failure.
4. User confirmed `OPENAI_API_KEY` exists in the original checkout's `.env`; credentials are **not
   claimed missing**. Root `.env` was neither read nor copied. Runtime `OPENAI_MODEL`, account access
   and permissions remain unverified; do not assume the existence of a key establishes live access.

**AC13: UNVERIFIED.** The smoke artifacts are explicit blocker gates, not a completed live runner:
`.venv/bin/python scripts/demo_live.py --live` exits **2** with a sanitized prerequisite report.
`AGENT_CORE_LIVE=1 .venv/bin/pytest tests/live/test_agents_api.py -v` fails explicitly until the
above integration work is complete; default CI skips this acceptance gate and calls no live API.
`AGENT_CORE_LIVE` is a test-only opt-in flag, not a new runtime setting.

References verified during T03:
[official session lifecycle](https://developers.openai.com/api/docs/guides/agents-api/sessions),
[function required actions](https://developers.openai.com/api/docs/guides/agents-api/tools/functions),
[events and items](https://developers.openai.com/api/docs/guides/agents-api/sessions/events).
The live adapter cannot pass create-session conformance until the shared amendment is available;
this task remains Blocked overall, with the offline module committed for T01 review.
