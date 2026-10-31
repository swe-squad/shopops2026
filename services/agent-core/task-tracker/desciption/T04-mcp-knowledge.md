# T04 MCP Bridge Fixtures and Knowledge Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Track progress with checkboxes.

**Goal:** Supply scoped MCP data/knowledge/history capabilities with deterministic sample data and a bridge reusable for real endpoints.

**Architecture:** Application function tools are allowlisted and translated to fixed MCP tools. A real MCP client calls Streamable HTTP servers; short-lived scoped credentials enforce tenant/shop/user/conversation isolation on the server side.

**Tech Stack:** Python, MCP client/server, JSON Schema, Markdown/JSON knowledge, pytest and loopback HTTP.

**Spec:** [Agent Core Template Spec](../../agents_api_template_spec.md), sections 2–3, 7–9 and 11.

**Tracker and global constraints:** [Task list](../task_list.md). Owner: MCP/knowledge developer. Status: **Not started**.

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

- [ ] **Worktree baseline:** Record the foundation SHA, read service `AGENTS.md`, run `make install`, the available baseline tests and `make lint` in this worktree. Verify MCP test fixtures allocate their own ports and runtime data.
- [ ] **Contract tests first:** Create `tests/tools/test_schemas.py` for inclusive ISO dates, `start_date <= end_date`, maximum 90-day range, SKU length 1–64, limits 1–20 and result maximum 32 KiB. Assert rejection of undeclared identity, SQL, path, URL and arbitrary tool-name arguments.
- [ ] **Fixtures and knowledge:** Create two shops and at least two users' data references compatible with T02. Use absolute dates and SKU-A baseline 100 orders/5 returns versus current 100/15. Include sizing-complaint evidence and an immutable knowledge manifest with ID/version/checksum/documents. Verify calculated rates 5%, 15% and a 10 percentage point change.
- [ ] **Scoped credential tests first:** Add `tests/tools/test_credentials.py` for invalid signatures, expiry, wrong issuer/audience, mismatched shop/conversation and missing claims. Assert rejection before any repository or dataset access; model-supplied identity must never override signed scope.
- [ ] **MCP servers:** Implement `/mcp/data` and `/mcp/knowledge-memory` factories with Streamable HTTP. Validate credentials and scope for every call. Provide lexical knowledge search, version references and current-conversation history through the injected repository; no unrestricted writes/deletes.
- [ ] **Bridge/client:** Publish only allowlisted function tools, map to fixed MCP names, inject server-side scope/credentials/version, validate arguments/results and normalize protocol/tool errors. New tools discovered upstream remain unavailable until explicitly approved in configuration.
- [ ] **Failure and endpoint tests:** Add `tests/tools/test_bridge.py` for `not_found` versus empty dataset, permission denial, malformed output, timeouts, unexpected redirects, unsupported URL schemes and metadata targets. Enforce 15-second call timeout and at most two retries only for transient read-only failures. Do not retry permission/validation errors.
- [ ] **Real transport tests:** Add `tests/mcp/test_transport.py` with actual loopback HTTP calls to both servers. Prove cross-shop denial, history-owner isolation, correct bundle version, bounded output and deterministic metrics. An in-process function mock alone is not MCP protocol evidence.
- [ ] **Remote profile:** Use the same schemas with a configurable real endpoint. Disable mock Data MCP in remote mode and fail on missing remote URL/auth compatibility. Give T01 tests showing existing conversations retain pinned profiles while new ones use the activated revision.
- [ ] **Handoff:** Supply server factories, bridge factory, versioned schemas, auth documentation, fixtures and scoped test results. Request required runtime variables/dependencies from T01; do not edit shared build files independently.

## Verification and completion

After T01 scaffolding, run from `services/agent-core/`:

```bash
.venv/bin/pytest tests/tools tests/mcp -v
```

Expected: tool schemas, scoped tokens, deterministic metrics and real loopback MCP transport pass without OpenAI or external network access. T01/T02 integration additionally proves repository-backed history isolation and revision pinning; T03 live integration proves the provider can complete a real MCP-backed function call.

Primary criteria: AC03, AC04 and AC07; support AC05, AC10, AC12–AC14. Mark **Ready for integration** until factories are mounted and real history repositories are connected. Use commits such as `feat(agent-core): add scoped MCP knowledge tools`.

## Handoff record

Record the actual worktree path, branch, foundation SHA, result commit SHA, changed paths, transport/security test results and blockers here. Confirm all task changes are under `services/agent-core/`. T01 updates the central tracker and integrates the handoff; preserve the worktree until its commits are integrated or otherwise retained and it is clean.
