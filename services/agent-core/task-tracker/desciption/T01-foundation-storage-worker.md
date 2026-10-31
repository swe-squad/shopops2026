# T01 Foundation Storage and Worker Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Track progress with checkboxes.

**Goal:** Establish shared contracts, implement durable storage and execution, and integrate the four workstreams into a deployable service.

**Architecture:** The API persists work before returning `202`. A single service worker claims runs transactionally and coordinates provider events and scoped tool execution through interfaces supplied by T03 and T04.

**Tech Stack:** Python/FastAPI, SQLite, pytest, Docker, CapRover.

**Spec:** [Agent Core Template Spec](../../agents_api_template_spec.md), sections 1–6 and 8–12.

**Tracker and global constraints:** [Task list](../task_list.md). Owner: integration lead. Status: **Ready for integration**.

**Difficulty:** D5 — Very hard. This task combines contract ownership, atomic persistence, concurrency, uncertain provider outcomes, restart recovery and final integration. Its foundation must ship as a small first commit so the other three workstreams can start.

## Repository scope and worktree

Read the tracker's **Required repository workflow** and **Separate worktrees** sections before coding. Follow root/service instructions and the existing FastAPI template; all changes, including tooling and docs, stay inside `services/agent-core/`. Shared root files and other services are read-only.

Use branch `feat/agent-core-t01-foundation` in the dedicated `agent-core-t01` worktree; Git fallback: `/tmp/shopops2026-agent-core/T01`. Run service commands from `<worktree>/services/agent-core/`. Own service-local scaffolding only, not repository-wide infrastructure. Publish the verified foundation commit SHA before T02–T04 start, and coordinate their result commits through the local integration branch.

## File ownership

Paths below are relative to `services/agent-core/`. You are not alone in the codebase: preserve other owners' edits and coordinate interface changes rather than reverting them.

| Create or maintain | Responsibility |
| --- | --- |
| `app/contracts/{identity,models,errors,repository,provider,tools}.py` | Shared typed boundaries and errors |
| `contracts/README.md` | Shared contract decisions and change process |
| `app/config/{settings,registry}.py`, `config/registry.json` | Settings validation and immutable configuration revisions |
| `app/storage/{database,repositories}.py`, `app/storage/migrations/` | Schema, transactions, scoped persistence |
| `app/runs/{worker,state,recovery}.py` | Run claiming, provider/tool coordination, cancellation and reconciliation |
| `app/main.py`, `app/__init__.py` | App factory, lifespan, route/MCP mounting and dependency wiring |
| `tests/contracts/`, `tests/storage/`, `tests/runs/`, `tests/integration/`, `tests/conftest.py` | Shared fixtures and integration/recovery checks |
| `AGENTS.md`, `README.md`, `.env.example`, `.gitignore`, `.dockerignore`, `service.json`, `Dockerfile`, `Makefile`, `pyproject.toml`, `requirements*.txt`, `captain-definition` | Service-local scaffolding and shared build/runtime setup |
| `scripts/{demo_offline,cleanup_conversation}.py` | End-to-end offline demo and scoped cleanup/retention commands |

Do not implement T02 routes/auth, T03 provider internals, or T04 tools/MCP internals. Request their public interfaces and perform composition here.

## Interfaces and dependencies

Publish concrete types and complete signatures at the foundation gate before consumers write implementations. Required repository entry points include:

- `provision(scope, template_id, config_revision)` and `create_conversation(scope, orchestrator_id, client_conversation_id)` return typed records plus a created/replayed indicator.
- `enqueue_message(scope, conversation_id, client_message_id, content)` atomically returns persisted message/run IDs and replay state, or a typed conflict.
- `get_run(scope, run_id)`, `get_history(scope, conversation_id, after, limit)`, and `get_events(scope, run_id, after, limit)` enforce authorization scope and stable pagination.
- `claim_next_run()`, `save_session_mapping(...)`, `record_tool_result(...)`, and conditional `transition_run(...)` support durable worker progress without exposing raw SQL to consumers.
- `get_config_snapshot(...)` returns immutable knowledge/MCP/model configuration pinned to the conversation.

Choose precise argument and return types in `app/contracts/` and publish them in `contracts/README.md`. The names above are required operations, not permission for each owner to invent incompatible signatures. T03 supplies `AgentProvider`; T04 supplies `ToolBridge`; T02 supplies router/auth factories. The worker injects these dependencies and never imports their concrete implementation details.

## Implementation checklist

- [x] **Foundation:** Read the repository workflow and adapt `template/python-fastapi` plus `template/_shared` into the existing service directory without changing either template or the shared scaffold script. Preserve current documents; include service-local ignore files. Retain Python 3.14, Ruff py314/100, pinned dependency files and the template Makefile commands. Publish the tracker foundation gate, including revision activation and recovery-deadline decisions. Verify contracts import without provider/network initialization, then publish the foundation commit SHA for the other worktrees.
- [x] **Storage tests first:** Add `test_provision_concurrent_unique`, `test_enqueue_replay_before_busy`, `test_same_key_different_payload_conflicts`, and `test_cross_scope_repository_access_denied` in `tests/storage/test_repositories.py`. Require one orchestrator/run, stable replay IDs, typed conflicts, and no cross-scope result. Run the tests and confirm failure before implementing repositories.
- [x] **Storage implementation:** Add UUID/UTC tables, foreign keys, unique constraints, WAL/busy timeout, short transactions, config snapshots and stable cursor validation. Persist message/run/lock atomically; deduplicate provider items and tool calls.
- [x] **Worker tests first:** Add `test_only_one_active_run_per_conversation`, `test_restart_resumes_queued_run`, `test_replayed_tool_result_not_executed_again`, and `test_unknown_submission_blocks_conversation` in `tests/runs/test_recovery.py`. Use a controllable clock and T03 fake provider; assert no automatic input resubmission after an uncertain provider outcome.
- [x] **Worker implementation:** Coordinate `queued`, `running`, `waiting_tool`, `reconciling`, and terminal states. Enforce 180-second run deadlines, 8 calls/run and 4 concurrent runs. Confirm provider cancellation/root-turn completion before unlocking; persist result before tool-result delivery.
- [x] **Runtime guards:** Test that missing required configuration fails without exposing values and that fake provider/fixture auth fail outside local/test. Implement readiness from DB/config/worker heartbeat and safe status metrics/logs.
- [ ] **Offline integration:** Wire T02–T04 through the app factory. Add `tests/integration/test_offline_workflow.py`: provision → create conversation → submit → poll → MCP data/knowledge → history/follow-up. Use real loopback MCP transport and fake provider.
- [ ] **Recovery and configuration integration:** Add tests for lost streams, duplicated provider events, source validation, endpoint revision pinning, worker restart and uncertain cancellation. Record a documented admin procedure for changing the active revision while preserving existing conversations.
- [x] **Packaging:** Copy config/knowledge/fixtures into the image, make `/data` writable for the non-root user, and document single-instance deployment with no overlapping DB users. Verify persistence after container restart with a volume. Do not deploy or configure external secrets as part of this task without authorization.
- [x] **Cleanup and handoff:** Implement scoped conversation/provider-session cleanup and history/event retention. Keep failed provider deletion visible. Complete README, `.env.example`, offline demo and validation evidence.

## Verification and completion

After scaffolding, run from `services/agent-core/`:

```bash
.venv/bin/pytest tests/contracts tests/storage tests/runs tests/integration -v
make ci
make docker
```

Expected: all selected tests and CI pass; image builds; recorded volume-restart check retains mappings/history/runs. Configure tests to prohibit external network access while permitting loopback. A successful image build alone is not deployment validation.

Primary criteria: AC01, AC06, AC08–AC12; integration support for all remaining criteria. Mark this task **Ready for integration** until T02–T04 are wired and the offline flow is proven. AC13 evidence comes from T03; if unavailable, record it as unverified rather than claiming complete live acceptance.

Use scoped commits such as `feat(agent-core): add durable run persistence`. Stage only this task's files and agreed shared changes.

## Handoff record

Record the actual worktree path, branch, reviewed baseline/foundation SHA, result commit SHA, changed paths, verification results and blockers here when implementation begins. Confirm the final branch changes only `services/agent-core/`. Update the central tracker after accepting the other owners' handoffs; retain their branches/worktrees until their commits are integrated and clean.

### Delivered module (2026-10-31)

- Worktree: `/home/khalee-dev/.codex/worktrees/2ccf/shopops2026` (native managed worktree).
- Branch: `feat/agent-core-t01-foundation`; local integration branch: `feat/agent-core-template`.
- Reviewed docs baseline: `b43f461` (only service spec/tracker files; unrelated dirty files preserved).
- Initial foundation: `9ce01a24f19acdfc4e5803faec1e1a3fa1fd678f`.
- Shared contract amendment: `94ef8f9c4e25e0af4e321865378bdce718b5fdba`.
  New T02–T04 worktrees may start here; existing initial-foundation worktrees import this commit.
  Scope now carries trusted permissions; Run pins enqueue-time scope and user-message receipt metadata.
- Implementation result: `54c8711124b0d3b7583d2d14c560ecc2d29dec54`.
- Result paths: `app/contracts/`, `contracts/README.md`, `app/config/`, `app/storage/`,
  `app/runs/`, `app/main.py`, `config/registry.json`, `scripts/`, `tests/contracts/`,
  `tests/storage/`, `tests/runs/`, `tests/integration/`, `tests/conftest.py`, and service-local
  scaffold/build/runtime/docs files. Final changed-path audit permits only `services/agent-core/`.
- Worktree/commits are retained locally. No push, deployment, external secret setup, or PR was performed.

### Verification evidence

- Contracts verified RED→GREEN before foundation publication; imports require no config/network/provider.
- Storage tests verified concurrent unique provisioning, replay before busy, payload conflicts,
  tenant/shop/user isolation, resource-bound cursors, immutable revision activation and snapshots.
- Worker tests verified transactional claims, four-run/eight-call limits, queued restart, durable tool
  replay, stream loss, subagent events, unknown submission/session creation, cancellation confirmation,
  source rejection, provider-event deduplication and deadline enforcement before tool delivery.
- Runtime tests verified safe configuration errors, fake/fixture restrictions, one DB owner,
  shared dependency composition, mounted MCP app lifespan and visible provider cleanup failure.
- `make ci` with Python 3.14.7: **43 passed**, Ruff lint/format passed.
  One upstream Starlette TestClient/httpx deprecation warning remains; no tests failed or skipped.
- `make docker`: **PASS**, image `agent-core:latest`, non-root UID 1001, writable `/data`.
- `.venv/bin/python -m scripts.verify_volume_restart`: **PASS**. Two containers with
  `--network none` and one temporary volume preserved orchestrator/conversation/run IDs, provider
  mapping, user/assistant history, pinned revision and queued work after container recreation.
  The script removes only its uniquely named test volume in a finally block.
- Container smoke: **PASS**, `/health` 200 and `/ready` 503 while T02–T04 adapters are absent.
- Fresh whole-change review found five P1 issues; all were reproduced RED and corrected GREEN:
  durable permission propagation, cancellation draining SQLite threads before ownership release,
  invalid output after confirmed completion, stable replay after retention and tool delivery deadlines.
  Full suite passed after the fix pass; no second reviewer pass was represented as performed.
- `graphify update .`: **PASS** inside this service, AST-only, no API calls. SQL AST extraction is
  partial because `tree_sitter_sql` is not installed. Graph/evidence outputs remain ignored.
- Local evidence: `.evidence/{make-ci-final.log,docker-build-final.log,volume-restart-final.log,
  container-readiness.log,graphify-update-final.log}`. Runtime DBs/environments were not committed.

### Remaining integration prerequisites

- T02: authenticated API/router factory and fixture/JWT implementation; no handoff exists yet.
- T03: fake/live AgentProvider factories and verified/pinned SDK exposing `beta.agents`; no handoff yet.
  Actual OpenAI session/tool/follow-up cleanup evidence (AC13) is **UNVERIFIED**.
- T04: ToolBridge and real MCP ASGI factories, schemas, signed credentials, fixture data and knowledge;
  no handoff yet. Real loopback MCP transport and 5%→15% data evidence are **UNVERIFIED**.
- Full `tests/integration/test_offline_workflow.py` and offline API demo await those three handoffs.
  Current integration tests use explicit test-only provider/bridge doubles and lifecycle ASGI apps;
  they do not establish real MCP or live Agents API acceptance.
- Cross-owner contract review remains at consumer handoff. Published v1 interfaces unblock their
  implementation; no agreement from absent owners or completion of their tasks is claimed.
- Production/develop CapRover apps, volume strategy preventing overlap, JWT issuer/JWKS and runtime
  credentials remain deployment prerequisites. No public MCP ingress is configured by this task.

T01 remains **Ready for integration**, rather than Done, until the missing handoffs are composed and
full offline flow/security/recovery checks pass. Preserve other owners' branches/worktrees.
