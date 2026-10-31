# T02 Authentication and Application API Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Track progress with checkboxes.

**Goal:** Expose validated, scoped application endpoints with fixture/JWT authentication and predictable idempotency responses.

**Architecture:** FastAPI routers consume shared AuthContext and repository interfaces. Routes persist work through T01 and return polling resources; they never invoke the provider or implement the run worker.

**Tech Stack:** FastAPI, Pydantic, JWT/JWKS verification, pytest/TestClient.

**Spec:** [Agent Core Template Spec](../../agents_api_template_spec.md), sections 3–5, 8 and 11.

**Tracker and global constraints:** [Task list](../task_list.md). Owner: API/auth developer. Status: **Not started**.

**Difficulty:** D3 — Moderate. The endpoint structure is conventional, but JWT verification, ownership checks, response sanitization and replay-before-busy behavior require careful tests. Database transactions and worker recovery remain T01 responsibilities.

## Repository scope and worktree

Read the tracker's **Required repository workflow** and **Separate worktrees** sections before coding. Follow the existing FastAPI app factory, Pydantic/type-hint conventions, TestClient, service-local `.venv` and Makefile. All changes stay inside `services/agent-core/`; root files, shared templates/workflows and other services are read-only.

Use branch `feat/agent-core-t02-api-auth` in the dedicated `agent-core-t02` worktree; Git fallback: `/tmp/shopops2026-agent-core/T02`. Start from T01's published foundation commit SHA. Run commands from `<worktree>/services/agent-core/`, with a private environment/database and ephemeral test ports. Request shared dependency changes from T01 and import the reviewed commit instead of editing shared files independently.

## File ownership

Paths are relative to `services/agent-core/`. You are not alone in the codebase: do not revert other owners' edits. Request shared contract or dependency changes from T01.

| Create or maintain | Responsibility |
| --- | --- |
| `app/auth/{dependencies,fixture,jwt}.py` | Bearer authentication, AuthContext construction and permission checks |
| `app/api/{router,schemas,orchestrators,conversations,runs,health}.py` | Typed routes, errors, request/response validation and health endpoints |
| `fixtures/identities.json` | Synthetic users, memberships, permissions and fixture token mappings |
| `contracts/application-api.md` | HTTP examples, status codes, pagination and auth claims |
| `tests/auth/`, `tests/api/` | JWT, scope, validation, replay and response-sanitization tests |

T01 owns `app/main.py`, shared contracts, test root fixtures, README, settings and dependencies. T04 owns scoped MCP credentials; do not create a second MCP token implementation in auth.

## Interfaces and dependencies

- Consume `AuthContext`, `Scope`, typed repository results/errors and cursor types from T01's foundation gate.
- Provide `authenticate(token: str) -> AuthContext` as an async auth-adapter operation and `build_api_router(...) -> APIRouter` with dependencies defined at the gate.
- Consume repository operations `provision`, `create_conversation`, `enqueue_message`, `get_run`, `get_history`, and `get_events`; use in-memory stubs for module tests until T01 storage is ready.
- Consume an injected readiness probe from T01; do not start a worker inside a route or call OpenAI for health checks.
- Coordinate synthetic identity IDs with T04 so two shops and multiple users are exercised by the same fixture profile.

## Implementation checklist

- [ ] **Worktree baseline:** Record the foundation SHA, read service `AGENTS.md`, run `make install`, the available baseline tests and `make lint` in this worktree. Report pre-existing failures separately from task regressions.
- [ ] **Auth tests first:** Create `tests/auth/test_auth.py` with cases for missing/malformed bearer tokens, invalid signature/issuer/audience/expiry, missing claims, invalid membership types, fixture token mapping and denied permissions. Use local keys/JWKS fixtures; do not require a real identity provider.
- [ ] **Auth implementation:** Verify an explicitly allowed signing algorithm and all required claims. Produce trusted AuthContext; never accept tenant/user identity from the prompt or unverified headers. Fixture auth remains local/test only, with the startup restriction owned by T01.
- [ ] **API schemas/tests first:** Add Pydantic request/response models and tests in `tests/api/test_validation.py`. Assert trimmed content length 1–8000, body maximum 64 KiB, client IDs at most 128 characters, `limit` 1–100/default 50, and rejection of malformed/scoped cursors.
- [ ] **Provisioning and conversation endpoints:** Implement `POST /api/v1/shops/{shop_id}/orchestrator` and `POST /api/v1/shops/{shop_id}/conversations`. Test create `201`, same-input replay `200`, different revision/payload `409`, and foreign orchestrator/shop rejection.
- [ ] **Message endpoint:** Implement `POST /api/v1/conversations/{id}/messages`. Test `202` after persistence, replay returning the same IDs even while busy, new input while busy returning `409 conversation_busy`, and conflicting payload returning `409 idempotency_conflict`. Do not implement transaction logic in the route.
- [ ] **Read endpoints:** Implement `GET /api/v1/runs/{id}`, `/runs/{id}/events`, and `/conversations/{id}/history`. Test cross-tenant, cross-shop and same-shop/different-user access as `404`; missing operation permission within scope as `403`. Validate conversation ownership before exposing events or polling URLs.
- [ ] **Health and errors:** Implement `GET /api/v1/health` and `/ready` with the injected probe. Test liveness without OpenAI, readiness `503`, stable error envelope and exclusion of provider IDs, raw exceptions, credentials, chain of thought and raw provider events from public schemas.
- [ ] **Contract handoff:** Export OpenAPI/examples and document JWT claims and HTTP statuses. Give T01 the router/auth factories; connect real repositories in integration tests and resolve mismatches with their owner.

## Verification and completion

After T01 scaffolding, run from `services/agent-core/`:

```bash
.venv/bin/pytest tests/auth tests/api -v
```

Run each new behavior test before implementation to observe failure, then again to confirm the implementation. Expected final result: auth/API tests pass using local fixtures/stubs without OpenAI or external network access. Integration with T01 must additionally prove persisted replay behavior and repository-level isolation; route-only mocks do not establish those guarantees.

Primary criteria: AC05 and AC14; support AC01, AC02, AC06 and AC12. Handoff includes router factories, documented claims/OpenAPI, test command/output, and remaining integration prerequisites. Mark **Ready for integration** until real storage is connected. Use commits such as `feat(agent-core): add scoped conversation endpoints`.

## Handoff record

Record the actual worktree path, branch, foundation SHA, result commit SHA, changed paths, verification results and blockers here. Confirm all task changes are under `services/agent-core/`; leave the central tracker update and final integration to T01. Do not delete the worktree until its commits are preserved and it is clean.
