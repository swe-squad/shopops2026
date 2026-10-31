# T04 MCP Bridge Fixtures and Knowledge Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Track progress with checkboxes.

**Goal:** Supply scoped MCP data/knowledge/history capabilities with deterministic sample data and a bridge reusable for real endpoints.

**Architecture:** Application function tools are allowlisted and translated to fixed MCP tools. A real MCP client calls Streamable HTTP servers; short-lived scoped credentials enforce tenant/shop/user/conversation isolation on the server side.

**Tech Stack:** Python, MCP client/server, JSON Schema, Markdown/JSON knowledge, pytest and loopback HTTP.

**Spec:** [Agent Core Template Spec](../../agents_api_template_spec.md), sections 2–3, 7–9 and 11.

**Tracker and global constraints:** [Task list](../task_list.md). Owner: MCP/knowledge developer. Status: **Done** (module and local HTTP integration; external/live gates tracked separately).

**Difficulty:** D4 — Hard. Real MCP transport, bounded schemas, scoped token validation, retries and history isolation cross several security boundaries. Knowledge fixtures are straightforward; safe tool execution and compatibility with real endpoints drive the difficulty.

**OpenAI credentials:** `OPENAI_API_KEY` is not required for MCP/knowledge development or offline tests. Use a synthetic local `MCP_TOKEN_SIGNING_KEY` for scoped credential tests; it is separate from the OpenAI key. T03 supplies OpenAI credentials only for the integrated live smoke. See [OpenAI API key by task](../task_list.md#openai-api-key-by-task).

## Repository scope and worktree

Read the tracker's **Required repository workflow** and **Separate worktrees** sections before coding. Implement MCP modules inside the existing FastAPI service and keep its testing/dependency conventions. All schemas, data, knowledge and documentation stay inside `services/agent-core/`; do not create a separate MCP service, root package or workflow in this task.

Use branch `feat/agent-core-t04-mcp` in the dedicated `agent-core-t04` worktree; Git fallback: `/tmp/shopops2026-agent-core/T04`. Start from T01's published foundation commit SHA and run commands from `<worktree>/services/agent-core/`. Use a private fixture DB and ephemeral loopback ports to prevent collisions with other worktrees. Request shared dependency/configuration changes from T01 and import the reviewed commits.

## File ownership

Paths are relative to `services/agent-core/`. You are not alone in the codebase: do not revert other owners' changes. Coordinate shared contracts/dependencies with T01 and fixture identity IDs with T02.

| Create or maintain | Responsibility |
| --- | --- |
| `app/tools/{bridge,client,credentials,validation}.py` | Allowlist, MCP client, scoped token issuance/validation and bounded schemas |
| `app/mcp/{data,knowledge_memory}.py` | Mock Data and Knowledge–Memory MCP server factories |
| `knowledge/returns-v1/` | Immutable manifest and sample policy documents |
| `fixtures/business/returns-v1.json` | Synthetic metrics/reviews across shops |
| `contracts/tools/`, `contracts/mcp-integration.md` | Versioned tool JSON Schemas, error envelopes and auth contract |
| `tests/tools/`, `tests/mcp/` | Validation, credential isolation and real-transport contract tests |

T01 owns app mounting, configuration loading and history persistence. T03 owns provider events and application output normalization. Do not maintain duplicate worker or provider-result persistence in the bridge.

## Interfaces and dependencies

Consume T01's `Scope`, `ConfigSnapshot`, `PendingToolCall`, `ToolDefinition`, `ToolResult`, and scoped history repository interface. Expose `ToolBridge.execute(...) -> ToolResult` and factories for Data and Knowledge–Memory MCP ASGI applications; exact async arguments are frozen at the foundation gate.

Publish function/MCP schemas for `get_return_metrics(sku, start_date, end_date)`, `get_review_summary(sku, start_date, end_date)`, `search_knowledge(query, limit)`, and `get_conversation_history(before_sequence, limit)`. Scope, credentials and bundle version are server-controlled inputs, never model arguments.

T01 supplies an immutable runtime profile; T03 consumes published tool definitions. Use a history repository stub until T01 is ready. The credential implementation follows the gate's issuer/audience/expiry/algorithm/claims; it is shared by the bridge and both MCP servers.

## Implementation checklist

- [x] **Worktree baseline:** Record the foundation SHA, read service `AGENTS.md`, run `make install`, the available baseline tests and `make lint` in this worktree. Verify MCP test fixtures allocate their own ports and runtime data.
- [x] **Contract tests first:** Create `tests/tools/test_schemas.py` for inclusive ISO dates, `start_date <= end_date`, maximum 90-day range, SKU length 1–64, limits 1–20 and result maximum 32 KiB. Assert rejection of undeclared identity, SQL, path, URL and arbitrary tool-name arguments.
- [x] **Fixtures and knowledge:** Create two shops and at least two users' data references compatible with T02. Use absolute dates and SKU-A baseline 100 orders/5 returns versus current 100/15. Include sizing-complaint evidence and an immutable knowledge manifest with ID/version/checksum/documents. Verify calculated rates 5%, 15% and a 10 percentage point change.
- [x] **Scoped credential tests first:** Add `tests/tools/test_credentials.py` for invalid signatures, expiry, wrong issuer/audience, mismatched shop/conversation and missing claims. Assert rejection before any repository or dataset access; model-supplied identity must never override signed scope.
- [x] **MCP servers:** Implement `/mcp/data` and `/mcp/knowledge-memory` factories with Streamable HTTP. Validate credentials and scope for every call. Provide lexical knowledge search, version references and current-conversation history through the injected repository; no unrestricted writes/deletes.
- [x] **Bridge/client:** Publish only allowlisted function tools, map to fixed MCP names, inject server-side scope/credentials/version, validate arguments/results and normalize protocol/tool errors. New tools discovered upstream remain unavailable until explicitly approved in configuration.
- [x] **Failure and endpoint tests:** Add `tests/tools/test_bridge.py` for `not_found` versus empty dataset, permission denial, malformed output, timeouts, unexpected redirects, unsupported URL schemes and metadata targets. Enforce 15-second call timeout and at most two retries only for transient read-only failures. Do not retry permission/validation errors.
- [x] **Real transport tests:** Add `tests/mcp/test_transport.py` with actual loopback HTTP calls to both servers. Prove cross-shop denial, history-owner isolation, correct bundle version, bounded output and deterministic metrics. An in-process function mock alone is not MCP protocol evidence.
- [x] **Remote profile:** Use the same schemas with a configurable real endpoint. Disable mock Data MCP in remote mode and fail on missing remote URL/auth compatibility. Give T01 tests showing existing conversations retain pinned profiles while new ones use the activated revision.
- [x] **Handoff:** Supply server factories, bridge factory, versioned schemas, auth documentation, fixtures and scoped test results. Request required runtime variables/dependencies from T01; do not edit shared build files independently.

## Verification and completion

After T01 scaffolding, run from `services/agent-core/`:

```bash
.venv/bin/pytest tests/tools tests/mcp -v
```

Expected: tool schemas, scoped tokens, deterministic metrics and real loopback MCP transport pass without OpenAI or external network access. T01/T02 integration additionally proves repository-backed history isolation and revision pinning; T03 live integration proves the provider can complete a real MCP-backed function call.

Primary criteria: AC03, AC04 and AC07; support AC05, AC10, AC12–AC14. Mark **Ready for integration** until factories are mounted and real history repositories are connected. Use commits such as `feat(agent-core): add scoped MCP knowledge tools`.

## Handoff record

Record the actual worktree path, branch, foundation SHA, result commit SHA, changed paths, transport/security test results and blockers here. Confirm all task changes are under `services/agent-core/`. T01 updates the central tracker and integrates the handoff; preserve the worktree until its commits are integrated or otherwise retained and it is clean.


### T04 module handoff (2026-10-31)

- Worktree: `/tmp/shopops2026-agent-core/T04` (native-created worktree moved to the explicit
  task fallback path); implementation directory: `services/agent-core/`.
- Branch: `feat/agent-core-t04-mcp`; integration target: `feat/agent-core-template`.
- Foundation: `9ce01a24f19acdfc4e5803faec1e1a3fa1fd678f`.
- Shared amendment: T01 `94ef8f9` imported as `a244c9c`; no other T01 implementation imported.
  Trusted permissions now come from persisted `Run.scope`; ownership remains tenant/shop/user.
- Implementation result commit: `0f8d6b003d96f6ef7766a619c8bb352dfa48d533`. Handoff metadata follows
  in a separate documentation commit, so the code commit remains independently reviewable.
- Owned changes: `app/tools/`, `app/mcp/`, `contracts/tools/v1/`,
  `contracts/mcp-integration.md`, `fixtures/business/returns-v1.json`,
  `knowledge/returns-v1/`, `tests/tools/`, `tests/mcp/`, and this task description.
  Shared contract changes are exclusively the imported T01 amendment. The central tracker,
  application wiring, dependency files, image and other services are untouched by T04.
- Python: 3.14.7; isolated service `.venv`. `make install` succeeded. The host's default
  `python3` is 3.13; an ignored `.evidence/bin/python3` shim selects 3.14 for make commands.
- Baseline health/contracts: 3 passed before the amendment; existing source lint passed.
- Final `make ci PATH=<service>/.evidence/bin:/usr/local/bin:/usr/bin:/bin`: **103 passed**;
  Ruff check/format passed. Tests use real TCP loopback ephemeral ports plus TestClient;
  no OpenAI credentials or external service calls. Sandbox prevents loopback/TestClient
  execution, so these tests ran with approved sandbox escalation.
- Targeted coverage: 99 tool/MCP cases in the full run. Inclusive date/bounds, UTF-8 byte
  limit, exact baseline, empty/not-found/upstream failures, credential claims/signature/
  audience/expiry/owner/revision, trusted grants, metadata DNS (including mixed safe/unsafe
  answers), redirects, retry budget, JSON/SSE, session cleanup and 150-message pagination.
- One warning: upstream Starlette TestClient deprecates its current httpx adapter. No test
  failed; shared dependency upgrades remain T01's responsibility.
- Independent read-only review found four issues; regression tests reproduced and verified
  fixes for wrong baseline interval, unbounded DELETE body reads, cleanup after errors,
  and unrepresentable baseline dates. DELETE cleanup now runs in finally without reading
  the body and within the remaining total budget. No deferred review findings.
- `graphify update .` ran from the service directory (AST-only, ignored local graph outputs).
- Changed-path audit: `git diff --name-only <foundation>...HEAD`, staged/untracked paths
  and whitespace checks confirmed service-local paths only; the task branch/worktree is retained.

### Integration prerequisites and implementation decisions

See `contracts/mcp-integration.md` for full factory signatures, schemas, credential and
endpoint policy. T01 must promote the existing `httpx==0.28.1` pin to runtime, mount the
factories with the shared repository, include fixtures/knowledge in the image, retain trusted
run grants, validate remote profiles at activation and use canonical mounted URLs. Foundation
URL examples omit the trailing slash: use a coordinated new revision or exact-path dispatch;
redirects are intentionally rejected and persisted revision contents must not be rewritten.

The bridge/client implement the bounded MCP 2025-06-18 HTTP protocol with the already-present
httpx dependency. History adapts the frozen forward-cursor repository to before_sequence with
O(history) reads while retaining at most 20 messages. Data references from approved remote
servers may be opaque; the bridge checks source types and response/query consistency, while
T03 must validate that answer references are a subset of persisted successful tool results.
A remote service remains responsible for the existence of its opaque evidence references.

Production app mounting, SQLite-backed history ownership, administrative revision activation,
volume/recovery checks, TLS/SNI against a real remote peer and live provider tool delivery are
**unverified integration gates**, not module passes. T01/T02/T03 own those checks. MCP module
transport, owner isolation, deterministic 5%/15%/+10-point data and local old/new endpoint
pinning are verified. At module handoff this task was **Ready for integration**, not end-to-end Done. Preserve
this worktree and branch for the integration lead; no push, PR, merge or deployment is part
of the T04 handoff.

### Integration follow-up

T04 is now merged on `feat/agent-core-template`. The integration lead promoted the existing httpx
pin to runtime, mounted both subapps with real SQLite and added exact-path dispatch for v1 URLs.
Real HTTP tests now verify metrics, knowledge/history ownership, source references, one-session
follow-ups and readiness. Startup and revision activation reject unapproved remote profiles.
External TLS/SNI and live provider acceptance remain separate unverified gates.
