# T03 Agent Provider and Instructions Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Track progress with checkboxes.

**Goal:** Supply interchangeable fake/live Agents API adapters and grounded Vietnamese-response instructions without coupling provider code to worker or storage internals.

**Architecture:** A shared provider interface normalizes sessions, turns, pending actions, events and results. T01 owns durable scheduling/recovery; this adapter exposes enough provider state to reconcile safely.

**Tech Stack:** Python, official `openai` SDK, async transport interfaces, pytest with mocked transport.

**Spec:** [Agent Core Template Spec](../../agents_api_template_spec.md), sections 1–2, 4, 6–8 and 11.

**Tracker and global constraints:** [Task list](../task_list.md). Owner: agent/provider developer. Status: **Not started**.

**Difficulty:** D4 — Hard. Provider session/turn semantics, async stream recovery, pending actions, SDK compatibility and grounded output normalization must agree with the worker contract. Live access can block acceptance even when offline adapter tests pass.

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

- [ ] **Worktree baseline:** Record the foundation SHA, read service `AGENTS.md`, run `make install`, the available baseline tests and `make lint` in this worktree. Keep offline provider tests separate from opt-in live tests.
- [ ] **Prerequisite check:** Before implementing the live adapter, verify the official Agents API docs and installed SDK surface. Request a pinned SDK version exposing `beta.agents`; preserve `OPENAI_MODEL` configuration and distinguish unavailable credentials/access from code defects.
- [ ] **Conformance tests first:** Create `tests/providers/test_contract.py` covering lazy session creation, reuse, isolated sessions, pending function calls, tool-result submission, inspection, item retrieval and cancellation. Run against the fake implementation and a mocked live transport.
- [ ] **Fake provider:** Implement deterministic multi-turn scenarios: returns metrics, knowledge question, clarification, tool failure, duplicate event and interrupted stream. Invoke pending tool calls through the same protocol boundary as live execution; do not bypass T04 or return hardcoded successful integration evidence.
- [ ] **Live adapter:** Implement async session/input/event operations using the official SDK and no application credentials in agent context. Normalize transport errors with an explicit unknown-outcome marker; do not retry mutations or create replacement sessions implicitly.
- [ ] **Event/recovery tests:** Add `test_stream_loss_is_not_completion`, `test_subagent_completion_does_not_complete_root`, `test_pending_actions_require_current_provider_state`, and `test_timeout_submit_is_uncertain` in `tests/providers/test_events.py`. Expose provider IDs/state for T01 reconciliation without mutating the application DB.
- [ ] **Instructions and output tests:** Add `tests/agents/test_grounding.py` for Vietnamese answer instructions, missing-SKU/date clarification, no invented zero values, and rejection of source IDs absent from persisted tool results. Implement application response kinds `answer`, `clarification`, `cannot_answer`; do not assert exact model prose.
- [ ] **Capability profile:** Publish only approved tools from the pinned config; provide a delegation extension point without launching specialists. Do not allow prompts to override identity, MCP URLs, credentials or tool permissions.
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
