# Agent Core Template Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Checkboxes track implementation progress. This tracker does not authorize implementation or deployment by itself.

**Goal:** Deliver the Agent Core backend starter through four workstreams with explicit ownership and integration gates.

**Architecture:** FastAPI exposes scoped conversation APIs. A durable SQLite-backed worker coordinates the Agents API provider and application function tools bridged to internal MCP services.

**Tech Stack:** Python, FastAPI, SQLite, the official OpenAI SDK, MCP Streamable HTTP, pytest, Docker, and CapRover.

**Spec:** [Agent Core Template Spec](../agents_api_template_spec.md).

All implementation changes must stay inside `services/agent-core/`, the existing repository path (plural `services`, not `service`). Paths in task descriptions are relative to this service directory. A worktree contains the full repository, but its implementation working directory is `<worktree>/services/agent-core/`. All tasks are initially **Not started**; owner numbers are role placeholders, not assignments to named people.

## Task list

| ID | Task | Difficulty | Suggested owner | Status | Start dependency | Completion dependency |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | [Foundation, storage, worker, and integration](desciption/T01-foundation-storage-worker.md) | D5 — Very hard | Owner 1 / integration lead | Not started | None | T02–T04 handoffs for final integration |
| T02 | [Authentication and application API](desciption/T02-auth-application-api.md) | D3 — Moderate | Owner 2 | Not started | T01 foundation gate | T01 repositories and application wiring |
| T03 | [Agent provider and instructions](desciption/T03-agent-provider.md) | D4 — Hard | Owner 3 | Not started | T01 foundation gate | T01 worker and T04 bridge for live smoke |
| T04 | [MCP bridge, fixtures, and knowledge](desciption/T04-mcp-knowledge.md) | D4 — Hard | Owner 4 | Not started | T01 foundation gate | T01 history repository and application mounting |

The `desciption` directory spelling is intentional and follows the requested location. Do not rename it during implementation.

## Difficulty scale

Difficulty measures implementation complexity, failure modes, and integration burden; it is not a time estimate or an expansion of scope. D1 is a straightforward isolated change, D2 a small module with known boundaries, D3 a module with several validation/security paths, D4 a protocol or cross-module integration with recovery/security concerns, and D5 coordination across persistence, concurrency, recovery, and deployment. T01 is the largest and most critical workstream; publish its foundation separately so it does not block all parallel work.

## Required repository workflow

Read these sources before implementing any task:

1. [Root AGENTS.md](../../../AGENTS.md) and the service's `AGENTS.md` once T01 creates it; more-specific instructions apply.
2. [Python FastAPI instructions](../../../template/python-fastapi/AGENTS.md), [Makefile](../../../template/python-fastapi/Makefile), [project settings](../../../template/python-fastapi/pyproject.toml), and [service metadata](../../../template/python-fastapi/service.json).
3. [Service scaffold script](../../../scripts/new-service.sh), [shared CI](../../../.github/workflows/_ci.yml), and the relevant workflow sections of [deployment documentation](../../../docs/deploy-flow.md). Use current instructions and workflow code where older deployment examples differ from the present repo.

Reuse the existing `app/main.py` app factory, `app/` and `tests/` layout, service-local `.venv`, Python `3.14`, Ruff `py314` with line length `100`, and pinned `requirements.txt`/`requirements-dev.txt`. Use type hints, Pydantic request/response models and FastAPI TestClient. Keep blocking I/O out of async handlers. Preserve template Makefile targets `install`, `run`, `test`, `lint`, `format`, `docker`, and especially `ci`.

All created/modified source, tests, docs, scripts, config, ignore rules and build files belong under `services/agent-core/`. Root `AGENTS.md`, `.github/`, `template/`, `scripts/`, other services, and repository-wide dependency files are read-only for these tasks. Do not add a root test runner, workflow, shared package or deployment script. Put task-specific runtime artifacts in ignored service-local paths. If an external change is necessary, report the exact dependency rather than expanding scope.

T01 adapts the existing template into this already-present service directory, without deleting the directory or changing the shared scaffold script. Include service-local `.gitignore` and `.dockerignore`; ignore runtime DB files, caches, environments and generated evidence there. Do not create a differently named temporary service in the monorepo.

Use commits of the form `type(agent-core): message`. The completed integration branch opens a PR into `develop`; the existing pipeline discovers this service through `service.json` and runs `make ci`. Do not push to `develop`/`main` or trigger `/deploy` as an implementation verification step. Deployment setup and secrets remain documented prerequisites.

## Separate worktrees

Each task must execute in its own worktree and branch. A worktree is isolation, not permission to modify the rest of the monorepo. This plan records the setup; no worktrees have been created by this documentation update.

| Task | Branch | Worktree label | Git fallback path |
| --- | --- | --- | --- |
| T01 | `feat/agent-core-t01-foundation` | `agent-core-t01` | `/tmp/shopops2026-agent-core/T01` |
| T02 | `feat/agent-core-t02-api-auth` | `agent-core-t02` | `/tmp/shopops2026-agent-core/T02` |
| T03 | `feat/agent-core-t03-provider` | `agent-core-t03` | `/tmp/shopops2026-agent-core/T03` |
| T04 | `feat/agent-core-t04-mcp` | `agent-core-t04` | `/tmp/shopops2026-agent-core/T04` |

Prefer the platform's native worktree facility and record its actual path. If unavailable, use Git worktrees at the distinct fallback paths above, outside the checkout so no root `.gitignore` change is needed. Verify the destination is unused; reuse only a matching task worktree and never force-reset or overwrite another workspace. `/tmp` is temporary; commit task work before any cleanup. Worktree metadata and environment setup are operational artifacts, not additional implementation scope.

### Shared starting point

- [ ] Preserve unrelated dirty/untracked files. Commit only the reviewed service spec/tracker baseline before creating task worktrees; untracked files in the current checkout will not appear automatically in another worktree. Never copy the root `.env` or local credentials between worktrees.
- [ ] The integration lead prepares a local `feat/agent-core-template` branch from the reviewed project base. T01 starts from that baseline in its assigned worktree.
- [ ] T01 creates a small, independently verified foundation commit for scaffold/contracts. Record its exact SHA in the task handoff and make it available on the integration branch.
- [ ] Start T02–T04 branches/worktrees from that exact foundation commit, not from an unrelated `develop` tip or T01's uncommitted working directory. T01 continues storage/worker work in its own branch.
- [ ] Later shared contract/dependency changes are isolated T01 commits. Each task imports the same reviewed commits before continuing; do not copy files manually or cherry-pick another owner's entire unfinished branch.

### Isolation and integration rules

- Each worktree has its own service `.venv`, fixture DB, runtime data directory and ignored `.env` when needed. MCP tests bind ephemeral loopback ports; concurrently running development servers use distinct host ports. The container/service port remains `8000`.
- Run commands from `<worktree>/services/agent-core/`: `make install`, the task's targeted pytest command, and `make lint`. After dependencies are installed, offline tests prohibit external network calls. Dependency installation may require package-registry access; it is not an agent test.
- The integration lead alone edits shared scaffolding, dependencies and wiring. Owners update only their task description and owned files; T01 updates the central task table to avoid tracker merge conflicts.
- Before handoff, record worktree path, branch, base SHA, result commit SHA, changed paths, test commands/results and unresolved integration prerequisites in the task's description. Inspect `git diff --name-only <base-sha>...HEAD` and staged/untracked paths; all task changes must remain under `services/agent-core/`.
- The lead integrates committed task branches locally into `feat/agent-core-template`, resolves conflicts with the responsible owner, and runs full `make ci` plus integrated recovery/volume checks. Re-run affected tests after contract or wiring changes. Only the completed integration is proposed to `develop`.
- Remove worktrees only after commits are integrated or otherwise preserved and the worktrees are clean. Do not force-remove worktrees or discard unfinished changes.

## Global constraints

- Use OpenAI Agents API; do not substitute Agents SDK or a custom Responses API loop.
- Use one service on port `8000`, one replica, one application worker, and SQLite on a persistent volume.
- Keep tenant, shop, and user distinct; enforce scope in API, repositories, and MCP.
- Pin configuration per conversation. Never share provider sessions across conversations/users.
- Accept only one nonterminal run per conversation; distinguish replay from a new message.
- Defaults: run timeout `180` seconds, MCP timeout `15` seconds, `8` tool calls per run, `4` concurrent runs. Retry read-only transient MCP failures at most twice.
- User-facing answers remain Vietnamese. These task documents and implementation instructions are English.
- Default CI is offline: no OpenAI key and no network beyond loopback. Live integration evidence is recorded separately.
- Protect secrets and personal data; never log prompts, outputs, tool payloads, or credentials.
- Work on feature branches targeting `develop`. Preserve existing documentation and unrelated workspace changes.
- Every owner writes tests for their module. Only the integration lead edits shared wiring/dependency files; other owners submit explicit dependency requests.

## Foundation gate

T01 publishes the following before T02–T04 start production code. The other owners can review the spec, prepare test cases, and verify prerequisites while waiting.

- [ ] Preserve the current documents while scaffolding; `scripts/new-service.sh` rejects the existing `agent-core` directory.
- [ ] Publish the verified foundation commit SHA and start T02–T04 in separate worktrees from that commit.
- [ ] Publish `app/contracts/identity.py`, `models.py`, `errors.py`, `repository.py`, `provider.py`, and `tools.py`, plus `contracts/README.md` with field definitions and serialization rules.
- [ ] Define `AuthContext`, `Scope`, `ConfigSnapshot`, `Conversation`, `Run`, `RunEvent`, `Message`, `Page`, and explicit idempotent result types.
- [ ] Define `AgentProvider`, `ProviderEvent`, `ProviderSession`, `ProviderSnapshot`, `PendingToolCall`, `ToolDefinition`, `ToolResult`, and `ApplicationResponse`.
- [ ] Freeze method signatures, error classes, dependency injection, and transaction boundaries with the four owners. Use async interfaces consistently; keep blocking database/SDK work off the event loop.
- [ ] Define event ordering, cursor validation, root-turn identity, and tool-call deduplication rules. Provider code must not import worker implementation; MCP code must not import API routes.
- [ ] Document scoped credential issuer, audience, expiry, signing algorithm, and claims shared by the bridge and MCP servers. T04 owns its implementation.
- [ ] Resolve revision activation: the spec rejects provisioning a different revision but also requires new conversations to adopt changed configuration. Define and document the administrative activation procedure without silently changing the provisioning API.
- [ ] Set an explicit recovery deadline and post-timeout cancellation/reconciliation policy; unknown outcomes must not unlock or resubmit a conversation automatically.

`app/contracts/` is a proposed shared boundary package added by this plan. It is distinct from `contracts/`, which contains integration documentation and JSON Schemas. T01 owns shared Python types; T02 owns application API examples; T04 owns tool schemas. Contract changes require updating consumers and their fakes in the same coordinated change.

## Parallel execution and integration

| Milestone | Work that can run concurrently | Exit evidence |
| --- | --- | --- |
| M0 — Foundation | T01 scaffold/contracts; T02–T04 contract review and test design | Importable shared types and agreed signatures |
| M1 — Modules | T01 storage/worker; T02 API/auth; T03 fake/live adapters; T04 MCP/knowledge | Each module passes its scoped tests using fakes/stubs |
| M2 — Offline integration | T01 wires application; other owners resolve their integration issues | API → durable run → fake provider → real loopback MCP → history |
| M3 — Live and deployment validation | T03 leads live smoke; T01 container/recovery; T02/T04 security checks | Live evidence when credentials exist; offline CI and volume restart checks |

T01 is delivered in stages, not as a prerequisite that must be fully completed before all other tasks. Its final integration depends on their handoffs; there is no circular start dependency.

## Review focus

| Condition | Required behavior | Test owner |
| --- | --- | --- |
| A duplicate message is retried while its original run is busy | Return the existing run before applying the busy check | T01 storage + T02 API |
| A provider event or tool result is replayed after restart | No duplicate message/result, no extra provider turn | T01 worker + T03 adapter |
| Signed MCP credentials target a different conversation or audience | Reject before data access, even when model arguments look valid | T04 |
| A root turn remains active after an apparent transport failure | Reconcile or block; never treat stream closure as completion | T03 adapter + T01 worker |
| Output cites a fabricated source or returns oversized tool data | Fail validation/truncate only according to the documented contract; do not publish invented evidence | T03 output normalization + T04 bridge |

## Acceptance ownership

| Spec criteria | Primary owner | Supporting owners |
| --- | --- | --- |
| AC01, AC06 | T01 | T02 |
| AC02 | T03 | T01, T02 |
| AC03, AC04 | T04 | T03, T01 |
| AC05 | T02 | T01, T04 |
| AC07 | T04 | T01, T03 |
| AC08, AC09, AC11, AC12 | T01 | T02–T04 |
| AC10 | T01 | T04 |
| AC13 | T03 | T01, T04 |
| AC14 | T02 | T01, T03, T04 |

## Completion tracking

- [ ] T01 foundation gate published.
- [ ] Four separate task branches/worktrees recorded, with a shared committed foundation and no shared runtime data.
- [ ] T01 storage/worker module tests pass.
- [ ] T02 module handoff accepted.
- [ ] T03 offline module handoff accepted.
- [ ] T04 module handoff accepted.
- [ ] Offline integration, recovery, and isolation checks pass.
- [ ] `make ci` passes from the service directory.
- [ ] Container volume restart and readiness behavior verified.
- [ ] AC13 live evidence recorded, or explicitly marked unverified with the missing prerequisite. Unverified live acceptance must not be reported as passed.
- [ ] Each task status updated with validation evidence and remaining blockers.
- [ ] Final changed-path review confirms all implementation changes are under `services/agent-core/` and the integration PR targets `develop`.

Status vocabulary: **Not started**, **In progress**, **Ready for integration**, **Blocked**, **Done**. Use **Ready for integration** when module tests pass but required integration evidence is still missing.
