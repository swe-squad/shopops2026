# Agent Core Template Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Checkboxes track implementation progress. This tracker does not authorize implementation or deployment by itself.

**Goal:** Preserve the delivered T01–T04 conversation/tool baseline and deliver the hosted runtime extension through T05–T08, with explicit ownership and integration gates, then connect the existing chat client through T09.

**Architecture:** FastAPI exposes scoped conversation APIs. A durable SQLite-backed worker coordinates the Agents API provider and application function tools bridged to internal MCP services.

**Tech Stack:** Python, FastAPI, SQLite, the official OpenAI SDK, MCP Streamable HTTP, pytest, Docker, and CapRover.

**Spec:** [Agent Core Template Spec](../agents_api_template_spec.md).

For T01–T08, all implementation changes must stay inside `services/agent-core/`, the existing repository path (plural `services`, not `service`). Paths in task descriptions are relative to this service directory. A worktree contains the full repository, but its implementation working directory is `<worktree>/services/agent-core/`. T01–T04 statuses describe the delivered conversation/tool baseline; T05–T08 have delivered their offline modules; hosted live acceptance is tracked separately below. Owner numbers are role placeholders, not assignments to named people.

T09 is a separate client-integration milestone. Its proposed cross-service implementation scope is
explicitly listed in its description; this task-creation change edits only this service's tracker
and task description. It does not start implementation or change the T01–T08 ownership boundary.

## Task list

| ID | Task | Difficulty | Suggested owner | Status | Start dependency | Completion dependency |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | [Foundation, storage, worker, and integration](desciption/T01-foundation-storage-worker.md) | D5 — Very hard | Owner 1 / integration lead | Done | None | T02–T04 handoffs for final integration |
| T02 | [Authentication and application API](desciption/T02-auth-application-api.md) | D3 — Moderate | Owner 2 | Done | T01 foundation gate | T01 repositories and application wiring |
| T03 | [Agent provider and instructions](desciption/T03-agent-provider.md) | D4 — Hard | Owner 3 | Done | T01 foundation gate | T01 worker and T04 bridge for live smoke |
| T04 | [MCP bridge, fixtures, and knowledge](desciption/T04-mcp-knowledge.md) | D4 — Hard | Owner 4 | Done | T01 foundation gate | T01 history repository and application mounting |
| T05 | [Runtime foundation, persistence, artifacts API and integration](desciption/T05-runtime-foundation.md) | D5 — Very hard | Runtime integration lead | Ready for integration | Verified baseline containing the PR #5 live amendment | T06/T07 handoffs and T08 acceptance |
| T06 | [OpenAI-hosted provider and lifecycle](desciption/T06-hosted-provider.md) | D5 — Very hard | Provider developer | Ready for integration | Published T05 runtime foundation SHA | T05 wiring and T07 bundle for integrated live execution |
| T07 | [Versioned skills and specialist roles](desciption/T07-skills-specialists.md) | D4 — Hard | Capability developer | Ready for integration | Published T05 runtime foundation SHA | T06 runtime for real discovery/delegation evidence |
| T08 | [Hosted integration and live acceptance](desciption/T08-hosted-acceptance.md) | D5 — Very hard | Acceptance developer | Ready for integration | T05 foundation for fixture/test preparation | T05 wiring and T06/T07 handoffs for final verification |
| T09 | [Connect the chat client to Agent Core](desciption/T09-chat-client-integration.md) | D5 — Very hard | Client integration developer | Not started | `develop` containing merged PR #8; offline work may start now | Cross-service CI/recovery checks and gated hosted acceptance; unresolved T08 proof gates remain explicit |

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

## Published foundation

- Initial SHA: `9ce01a24f19acdfc4e5803faec1e1a3fa1fd678f`.
- Shared contract amendment/current starting SHA: `94ef8f9c4e25e0af4e321865378bdce718b5fdba`
  (local `feat/agent-core-template`); preserves trusted grants and replay receipts.
- Existing worktrees from the initial SHA import the amendment before integration.
- Worktree: `/home/khalee-dev/.codex/worktrees/2ccf/shopops2026`.
- T02–T04 may start now from the amended SHA; no dependency on unfinished storage/worker changes.
- Validation: contracts import without initialization, Ruff passes, contracts/health 3 passed.
- Shared types, factory signatures, revision activation and recovery rules: `contracts/README.md`.
- No T02–T04 worktrees were created by T01; each owner creates their own from the SHA above.
- Live provider SDK/MCP/auth implementations and their dependencies remain owned by T02–T04.

## Foundation gate

T01 publishes the following before T02–T04 start production code. The other owners can review the spec, prepare test cases, and verify prerequisites while waiting.

- [x] Preserve the current documents while scaffolding; `scripts/new-service.sh` rejects the existing `agent-core` directory.
- [x] Publish verified foundation and amendment SHAs (see above).
- [ ] T02–T04 owners create their separate worktrees from the amended SHA; T01 did not create them.
- [x] Publish `app/contracts/identity.py`, `models.py`, `errors.py`, `repository.py`, `provider.py`, and `tools.py`, plus `contracts/README.md` with field definitions and serialization rules.
- [x] Define `AuthContext`, `Scope`, `ConfigSnapshot`, `Conversation`, `Run`, `RunEvent`, `Message`, `Page`, and explicit idempotent result types.
- [x] Define `AgentProvider`, `ProviderEvent`, `ProviderSession`, `ProviderSnapshot`, `PendingToolCall`, `ToolDefinition`, `ToolResult`, and `ApplicationResponse`.
- [x] Publish v1 method signatures, error classes, dependency injection and transaction boundaries;
  async interfaces keep blocking SQLite work off the event loop.
- [ ] Confirm v1 consumer acceptance with T02–T04 at handoff; no absent-owner agreement is claimed.
- [x] Define event ordering, cursor validation, root-turn identity, and tool-call deduplication rules. Provider code must not import worker implementation; MCP code must not import API routes.
- [x] Document scoped credential issuer, audience, expiry, signing algorithm, and claims shared by the bridge and MCP servers. T04 owns its implementation.
- [x] Resolve revision activation: the spec rejects provisioning a different revision but also requires new conversations to adopt changed configuration. Define and document the administrative activation procedure without silently changing the provisioning API.
- [x] Set an explicit recovery deadline and post-timeout cancellation/reconciliation policy; unknown outcomes must not unlock or resubmit a conversation automatically.

`app/contracts/` is a proposed shared boundary package added by this plan. It is distinct from `contracts/`, which contains integration documentation and JSON Schemas. T01 owns shared Python types; T02 owns application API examples; T04 owns tool schemas. Contract changes require updating consumers and their fakes in the same coordinated change.

## Parallel execution and integration

| Milestone | Work that can run concurrently | Exit evidence |
| --- | --- | --- |
| M0 — Foundation | T01 scaffold/contracts; T02–T04 contract review and test design | Importable shared types and agreed signatures |
| M1 — Modules | T01 storage/worker; T02 API/auth; T03 fake/live adapters; T04 MCP/knowledge | Each module passes its scoped tests using fakes/stubs |
| M2 — Offline integration | T01 wires application; other owners resolve their integration issues | API → durable run → fake provider → real loopback MCP → history |
| M3 — Live and deployment validation | T03 leads live smoke; T01 container/recovery; T02/T04 security checks | Live evidence when credentials exist; offline CI and volume restart checks |

T01 is delivered in stages, not as a prerequisite that must be fully completed before all other tasks. Its final integration depends on their handoffs; there is no circular start dependency.

## OpenAI API key by task

| Task | Needs `OPENAI_API_KEY`? | When |
| --- | --- | --- |
| T01 | No for foundation, worker, and offline integration | Only if the integration lead personally runs the opt-in live smoke with T03 |
| T02 | No | Use local JWT keys and identity fixtures for auth/API tests |
| T03 | Yes for live Agents API calls | The live adapter smoke test and live demo require `OPENAI_API_KEY` and `OPENAI_MODEL`; fake-provider and mocked-transport tests do not |
| T04 | No for MCP/knowledge and offline tests | Use a synthetic local signing key for MCP credentials, not an OpenAI API key |

**Local source:** The original checkout's repository-root `.env` is known to declare `OPENAI_API_KEY`. It is local and untracked; linked worktrees do not automatically inherit it, and its value, validity and Agents API permissions have not been verified. Do not assume the service, SDK, or test runner automatically loads that file. Never commit, print, log, or paste its contents, or copy the entire root `.env` to a worktree.

For T03 live runs, supply `OPENAI_API_KEY` and `OPENAI_MODEL` to the process through the operator's environment or secret manager. Alternatively, the operator may configure a worktree-local, ignored `services/agent-core/.env` with the required values and explicitly load it using the service's documented configuration loader once implemented; merely creating the file does not prove it is loaded. The `.env.example` documents variable names and contains no real secrets. Production uses runtime secrets in CapRover. Never put the API key in an agent sandbox, prompt, MCP request, fixture, or test output.

Before the live smoke, check only that both variable names are set without printing their values; verify account/model access and API permissions through the live test. If credentials, permissions or model access are unavailable, continue offline work and record AC13 as **unverified**, not passed. T02/T04 do not need access to T03's secrets. Dependency installation may require registry access but does not require an OpenAI API key.

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

- [x] T01 foundation gate published.
- [x] Four separate task branches/worktrees recorded, with a shared committed foundation and no shared runtime data.
- [x] T01 storage/worker module tests pass.
- [x] T02 module handoff accepted.
- [x] T03 offline module handoff accepted.
- [x] T04 module handoff accepted.
- [x] Offline integration, recovery, and isolation checks pass.
- [x] `make ci` passes from the service directory.
- [x] Container volume restart and readiness behavior verified.
- [x] AC13 live evidence recorded, or explicitly marked unverified with the missing prerequisite. Unverified live acceptance must not be reported as passed.
- [x] Each task status updated with validation evidence and remaining blockers.
- [x] T01 changed-path audit confirms only `services/agent-core/` changed.
- [x] Template PR #4 was merged into `develop`; the live amendment is on `fix/agent-core-live`. No deployment was triggered by this amendment.

Status vocabulary: **Not started**, **In progress**, **Ready for integration**, **Blocked**, **Done**. Use **Ready for integration** when module tests pass but required integration evidence is still missing.

## T01 module handoff

Implementation result `54c8711124b0d3b7583d2d14c560ecc2d29dec54`: Python 3.14 CI passes
43 tests; Docker build, two-container volume persistence and foundation readiness behavior pass.
Five P1 review findings were fixed with RED→GREEN regressions. See T01's handoff record for paths,
commands and exact prerequisites. T02–T04 remain separate tasks; full offline MCP/API flow and AC13
are unverified. One upstream TestClient deprecation warning remains. No credentials were copied,
no remote push/deploy was performed, and all task changes stay inside the service directory.

## T01–T03 integration checkpoint (historical)

- Integration branch: `feat/agent-core-template`; isolated worktree: `/home/khalee-dev/.codex/worktrees/3913/shopops2026`.
- T01 base: `5d6bd78`; T02 branch merged as `ea759a6`; T03 branch merged as `835fabb`. All implementation changes stay inside this service.
- Default application startup now builds the T02 router using the same SQLite repository and selected fixture/JWT authenticator. Local/test fake-provider configuration selects T03's `FakeProvider`; explicit injected factories remain supported.
- Integrated tests prove API → SQLite → worker → T03 fake provider → test-only bridge, trusted grant propagation, idempotent replay/conflict, session reuse, cross-user/tenant isolation, and history/receipts after reopening the DB. T02's repository fake now compares identity without treating mutable permissions as ownership.
- The bridge used here is a test double, not T04's MCP transport. Readiness stays 503 without required MCP apps/bridge. No automatic live-to-fake fallback is enabled.
- Validation: full offline pytest suite **96 passed, 2 skipped**; `make ci` passed on Python 3.14.7 (including Ruff lint/format). One upstream Starlette/httpx deprecation warning remains. Skips are the opt-in live gate and optional official-SDK compatibility test (SDK dependency is not yet pinned/installed in this integration environment).
- Still pending: T04 bridge/MCP handoff, real loopback MCP workflow, coordinated initial-input session contract amendment, OpenAI SDK dependency pin, and AC13 live smoke. T03 remains Blocked for live execution; T01/T02 are not declared fully Done.
- Ruling: integrate existing modules and verify the offline boundary now; preserve the documented live-session blocker instead of silently changing the provider contract or introducing a sandbox. No push or deployment was performed.

- Independent read-only integration review found no concrete P0/P1 findings; it did not run its own tests. Verification above was run by the integration implementer.

## T04 integration checkpoint

- T04 handoff `dc0d999` (implementation `0f8d6b0`) has been merged into the integration branch. Shared amended grants are preserved.
- App startup now constructs the real MCP bridge and Data/Knowledge–Memory subapps with the same repository. Explicit injected test factories remain supported. Exact-path MCP dispatch preserves immutable v1 URLs without a redirect.
- Registry `approved_remote_profiles` explicitly gates real-profile compatibility; all registered URLs are allowlisted and validated before readiness or administrative activation. HTTP loopback is local/test-only.
- Real HTTP integration demonstrates API → SQLite → worker → fake provider → MCP metrics, knowledge and history, with source references, isolation, follow-ups and readiness. Provider reasoning remains simulated.
- Full offline verification: **198 passed, 2 skipped**, Ruff lint/format passed. Live gate and optional SDK check remain skipped; no real OpenAI request or credentials were used.
- Module handoffs are locally integrated; T03's live session contract/SDK pin and AC13 remain pending. T01/T04 are not declared end-to-end Done solely from module or fake-provider passes.

T02 and T04 are Done for their delivered modules and verified local integration. T01 remains pending final live composition; T03 remains Blocked on the explicitly documented live-session contract. These statuses do not mark AC13 passed.

Final T04 integration checks: `make ci` PASS (198 passed, 2 skipped); Docker build PASS; two network-isolated container restarts preserve volume data; runtime image imports API/provider/MCP composition. Independent read-only review found no concrete P0/P1 integration defects. Service-local AST graph updated; SQL extraction remains partial without tree_sitter_sql. No external API call, push or deployment occurred.

## Live acceptance checkpoint

The prior live blockers below/above are historical. The shared initial-input amendment,
atomic session/receipt persistence, live provider composition, source loader and official SDK
runtime pin are implemented. User authorization for synthetic live testing is recorded in T03.

AC13 opt-in pytest: **1 passed**, model `gpt-6-astra`, three completed turns in one session,
metrics/follow-up/knowledge grounded in real MCP fixture results, numeric checks and confirmed
remote/local cleanup. Aggregate evidence is local and ignored; no keys, prompts or model output
are committed. Normal CI remains offline and skips its single live-marked test.

T01–T04 are Done for the backend starter and local synthetic acceptance scope. Deployment and
real shop/identity/data-service onboarding remain separate system integration work.

Final live amendment validation: default `make ci` **207 passed, 1 skipped** (live gate opt-in); explicit live pytest **1 passed in 88.83s**, with 3 turns and confirmed remote/local cleanup. Model: gpt-6-astra. The pinned SDK wire test runs offline without skipping.

Live amendment packaging: Docker build PASS; SDK 3.42.0 imports in the runtime image; network-isolated volume recreation PASS. Independent review found a busy-run cleanup issue, reproduced by regression and fixed; follow-up read-only review found no remaining P0/P1 in the live delta. Live sessions were cleaned up; no deployment was performed.

Delivery note: template PR #4 was merged and its remote branch removed while live work was in progress. The live amendment is based on the updated origin/develop on branch `fix/agent-core-live`; the service tree is preserved by cherry-picking the verified amendment.

## Hosted runtime extension (T05–T08)

**Spec:** [Managed Codex Harness and OpenAI-hosted Runtime Extension](../agents_api_managed_runtime_spec.md). Status: T05–T08 integrated and verified offline; hosted live acceptance NOT ACCEPTED. This section refines the baseline workflow for T05–T08; it does not reopen T01–T04 or treat their acceptance as hosted evidence.

### Scope and starting point

- Documentation branch: `docs/agent-core-managed-runtime`, isolated worktree `/home/khalee-dev/.codex/worktrees/3913/shopops2026`; implementation baseline inspected at `271405fabfddd51c7bad1fa0a28e868cf6835967`, containing the PR #5 live fix. This is a reference baseline, **not** the T05 runtime foundation.
- At execution time, the lead selects a committed base containing the reviewed spec and live amendment. T05 publishes its actual foundation SHA below before consumer worktrees start code. Do not assume an old T01 foundation has runtime contracts.
- All implementation stays in `services/agent-core/`; shared repo instructions, Python 3.14, one SQLite owner/worker/replica, offline default CI and scoped secret handling still apply.
- T05 owns new shared contracts, settings/migrations, worker/composition/API wiring and dependency changes. T06/T07/T08 own only the files in their descriptions. You are not alone in the codebase: preserve other owners' edits; request shared changes as isolated T05 commits.

### New worktrees

| Task | Branch | Worktree label | Git fallback path |
| --- | --- | --- | --- |
| T05 | `feat/agent-core-t05-runtime-foundation` | `agent-core-t05` | `/tmp/shopops2026-agent-core/T05` |
| T06 | `feat/agent-core-t06-hosted-provider` | `agent-core-t06` | `/tmp/shopops2026-agent-core/T06` |
| T07 | `feat/agent-core-t07-skills-specialists` | `agent-core-t07` | `/tmp/shopops2026-agent-core/T07` |
| T08 | `feat/agent-core-t08-hosted-acceptance` | `agent-core-t08` | `/tmp/shopops2026-agent-core/T08` |

Prefer native worktree tools; no new task worktrees are created by this documentation update. Each gets its own venv, DB and ignored evidence. Never copy an env file or credentials from another worktree. Reuse a worktree only if its task/branch matches and it is clean; never reset another owner's workspace.

### T05 runtime foundation gate

- [x] Record baseline SHA, actual T05 worktree, foundation SHA and verification commands in T05's handoff. **Published runtime foundation SHA: `1e45865`; required shared amendment: `ebd7537`. Consumers start from `ebd7537`.**
- [x] Freeze runtime/bundle/environment/artifact types and repository/provider signatures in `app/contracts/runtime.py` and `contracts/managed-runtime.md`; make fakes and existing consumers import them.
- [x] Define legacy `none` normalization and new immutable hosted profiles; prove old records/config revisions remain usable.
- [x] Publish root/child/environment event correlation, artifact finalization, cleanup/recovery records and source-validation rules.
- [x] Verify SDK 3.42.0 hosted/plugin/environment/artifact surfaces offline; coordinate any required pin change. Do not call OpenAI merely to publish contracts.
- [x] Publish stubs/test doubles for bundle building, hosted environment building and artifacts so T06/T07/T08 can work without shared implementation edits.
- [x] Run foundation contract/migration tests and lint. Consumer owners record the exact imported SHA; do not claim agreement for absent owners.

### Parallel work and difficulty

T05 starts first and continues its storage/worker/API work after publishing the small foundation. T06 provider/lifecycle and T07 skills/specialists can then code in parallel. T08 can develop failure fixtures and acceptance tests from that same foundation, then run final integration after T05–T07 handoffs. The lead integrates into `feat/agent-core-hosted-runtime` and proposes a PR into `develop`; no task independently merges or deploys.

T05 is D5 because backward-compatible persistence, immutable profiles, root/child correlation and authorized artifact delivery cross the full service. T06 is D5 because provisioning and delete failures can leave billable/unknown remote resources and must recover without duplicate creation. T07 is D4 because deterministic bundle validation and skills/delegation must respect actual API restrictions. T08 is D5 because only provider-side command/child/artifact evidence can prove the complete flow and teardown.

### Acceptance and credentials

| Criteria | Primary owner | Supporting owners |
| --- | --- | --- |
| AC15, AC19 | T05 | T06, T08 |
| AC16, AC20, AC21 | T06 | T05, T08 |
| AC17, AC18 | T07 | T06, T08 |
| AC22 and AC01–AC14 regression | T08 | T05–T07 |

T05/T07 need no OpenAI key for normal work. T06/T08 need `OPENAI_API_KEY` and `OPENAI_MODEL` only for explicit hosted live runs through the documented loader/process environment. The original ignored root `.env` is not inherited and must never be copied; only the existing explicit credentials loader may read key/model at runtime. All tasks use synthetic fixture data. Hosted live tests will require **both** `AGENT_CORE_LIVE=1` and `AGENT_CORE_LIVE_HOSTED=1`; the flags and hosted command are now implemented by T08. See `contracts/hosted-acceptance.md`.

### Extension completion tracking

- [x] T05 runtime foundation published and accepted by consumers.
- [x] T05 runtime persistence/API/worker integration verified.
- [x] T06 hosted provider/lifecycle handoff verified.
- [x] T07 bundle/skill/specialist handoff verified.
- [x] T08 offline failure, isolation and baseline regression suite verified.
- [x] Real hosted code execution, approved skill use and two child identities recorded (partial live evidence; role binding remains unverified).
- [ ] Scoped report artifact and same-session follow-up verified.
- [x] Session removal and hosted cleanup request recorded; unresolved remote resources retained for recovery.
- [x] `make ci`, Docker build and volume restart checks pass after integration.
- [ ] All AC15–AC22 evidence recorded; unavailable live evidence remains explicitly unverified.

The original spec update delivered documentation only. The integration checkpoint below records subsequent code and verification; baseline completion flags are not reused as hosted evidence.

Historical documentation checkpoint (before implementation): the English runtime spec, baseline cross-references and four task descriptions were reviewed and validated as documentation only. Local link/anchor, code-fence, acceptance coverage, task ownership/status and service-scope checks pass; a builder review found no remaining plan-changing gap after report-mode compatibility was clarified. No runtime implementation or hosted live call was performed, and the T05 foundation was then unpublished.

## T05 offline handoff

T05 implementation `ebd7537` is ready for module integration on its assigned branch/worktree.
Foundation `1e45865` plus the shared-contract/lifecycle amendment are both required; consumers
start from `ebd7537`. Final Python 3.14 CI: 242 passed, 1 live skipped; Ruff, Docker build and
network-isolated runtime/artifact volume recreation pass. See T05's handoff for exact verification,
review corrections and pending gates. T06/T07 builder stubs deliberately fail closed. No consumer
handoff, hosted live acceptance, integration merge, remote push or deployment is claimed.

## Hosted integration checkpoint

Integration branch: `feat/agent-core-hosted-runtime`; managed worktree
`/home/khalee-dev/.codex/worktrees/3913/shopops2026`. T05 `428e2c7`, T06 `6e122fc`, and T07
`944481f` are integrated. The user subsequently confirmed T08 complete. Its implementation
`e648728` and handoff `6894bfb` were imported as `00d201d` / `e329467`; its separate worktree
remains intact. No uncommitted task files were copied.

- Setup fix `98ed1a2`: late first connection cannot bypass the 60-second setup budget. New
  regression was RED (completed instead of failed), then GREEN; established sessions keep their
  connected state and known late session/environment IDs remain available for cleanup.
- Wiring `5568975`: registered bundle version/digest, provider and startup path propagation,
  service-local path validation, Docker bundle packaging, and explicit hosted example profile.
  The default legacy registry stays unchanged; account/model and dev MCP endpoints remain explicit.
- Earlier T05–T07 verification: `make ci` **355 passed, 1 skipped**; lint/format PASS; Docker build PASS; the
  registered hosted plugin builds inside the UID1001 runtime image with networking disabled.
  Two network-isolated container recreations preserve legacy/runtime/artifact state.
- Fresh independent whole-branch review found one durable-timeout recovery issue, fixed in
  `de7b747` with a RED→GREEN restart regression. Review of the new T08 delta found one artifact
  delete acknowledgement issue, fixed in `9562b46` with three RED→GREEN cases. That commit also
  exposes all three hosted public errors and removes their strict xfail markers.
- T08 integrated scoped suite: **53 passed, 1 live skipped**. Full integrated `make ci`: **409 passed,
  2 live skipped, zero xfails**; Docker build and volume recreation PASS. Subsequent safe diagnostic
  additions are verified separately below.
- Final code verification at `7d2700d`: `make ci` **428 passed, 2 live skipped, zero xfails**;
  scoped T08 tests **72 passed**. Ruff, final Docker build and AST graph update PASS. Recorded
  network-isolated volume recreation preserves IDs, mappings, history, queue, config and artifacts.
- Four bounded real hosted attempts used SDK 3.42.0, `gpt-6-astra` and registered bundle `1.0.0`.
  All four confirmed session absence and local cleanup; no known live session is left for recovery.
  No physical sandbox-destruction claim is made from session deletion.
- Live-observed bash wrapping caused the initial saved-command proof rejection; `7d2700d` fixes
  that shape with RED→GREEN and wrapped adversarial tests. The final attempt passed the exact
  approved-helper and both skill checks before failing the required boundary-probe assertion.
- The final attempt completed the root, two child turns and nine command items; two backend MCP
  calls succeeded without worker/MCP errors. Both child task `instructions` fields were null,
  although completed child outputs were present. Role binding is therefore unverified under the
  frozen proof contract. The exact fixed probe command/denial proof also remains unverified.
- Aggregate actual evidence: ignored `.evidence/live-hosted-attempt1.json` through
  `.evidence/live-hosted-attempt4.json`; sanitized command-shape facts in
  `.evidence/live-proof-shape.json`. No raw command, prompt, payload or private ID is committed.
  Complete report download/numeric checks, follow-up, second-conversation isolation and AC22
  did not run past the proof gate and remain NOT ACCEPTED. There is no fallback or relaxed pass.
- Integration is reviewable as a draft PR into `develop`; real JWT/MCP/CapRover onboarding remains
  separate. Further paid attempts stopped after the final diagnostic run; no deployment occurred.

T08 now consumes the committed integration fixes and wiring. The original handoff records above
remain historical module evidence; actual live acceptance is recorded separately and cannot be
inferred from any offline count.


## Chat client integration follow-up (T09)

**Task:** [Connect the chat client to Agent Core](desciption/T09-chat-client-integration.md).
**Status:** Not started. **Difficulty:** D5 — Very hard. **Authentication:** demo phone number, no OTP.
**Planning baseline:** `53d094e`, the
`develop` merge of PR #8. This supersedes the earlier draft-delivery note for that PR only;
merging did not close the T08 live-proof gaps.

The selected integration keeps `shopops-chat` and its existing same-origin backend boundary:
`shopops-chat → shopops-chat-api → agent-core → OpenAI Agents API (openai_hosted)`.
The chat API adapts demo phone-number login (no OTP), per-user scope, durable application IDs,
run polling, history, navigation and downloads;
Agent Core alone owns provider sessions, tool execution, runtime recovery and report validation.

T09 can implement contract, UI and offline integration tests immediately from this committed
baseline. Its full hosted acceptance depends on T08's exact probe evidence and child-role proof
being accepted; unavailable evidence must remain unverified. Phone-demo identity and per-user isolation, honest
SSE/cancellation behavior and legacy database cutover are pinned in the task description.

Use a separate implementation branch `feat/shopops-chat-agent-core`, worktree label
`shopops-chat-agent-core`; Git fallback `/tmp/shopops2026-agent-core/T09`. Prefer a native managed
worktree and record its actual path. No T09 implementation worktree or code is created by this
planning change. The documentation branch is `docs/agent-core-chat-integration-task`, reusing the
clean managed worktree `/home/khalee-dev/.codex/worktrees/3913/shopops2026`; the original dirty
checkout and all module task worktrees are preserved.
