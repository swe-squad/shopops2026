# T05 Runtime Foundation, Persistence, Artifacts API and Integration

> **For agentic workers:** Use `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` when delegation is selected. Track work with checkboxes.

**Goal:** Publish the runtime foundation, preserve legacy conversations, and integrate scoped hosted execution and artifacts into the durable API lifecycle.

**Architecture:** Extend immutable shared contracts and SQLite records first. The existing worker remains a durable coordinator; provider/bundle implementations plug in after their separate handoffs.

**Tech Stack:** Python 3.14, FastAPI, SQLite, official OpenAI SDK, pytest, Docker and existing MCP transport.

**Spec:** [Managed runtime extension](../../agents_api_managed_runtime_spec.md), [main spec](../../agents_api_template_spec.md), [tracker](../task_list.md#hosted-runtime-extension-t05t08).

**Status:** Not started. **Difficulty:** D5 — Very hard. Migrations, snapshot compatibility, root/child identity, artifact security and remote cleanup cross the entire service.

## Global constraints

Read the root and service AGENTS.md, the main template spec, runtime extension spec, and the tracker's **Hosted runtime extension (T05–T08)** section first. All paths below are relative to `services/agent-core/`; root workflows/templates/scripts and other services are read-only. Use Python 3.14, pinned dependencies, Ruff line length 100, one SQLite owner/worker/replica and existing API scopes. Keep default CI offline except loopback. You are not alone in the codebase: preserve other owners' changes and import shared amendments from T05 rather than copying files.

Do not copy env files between worktrees or print credentials, prompts, model output, tool data or command output in logs/evidence. Existing `none` live evidence is not hosted acceptance. Work in the assigned separate worktree and keep a private venv/DB/evidence directory. Use commits `type(agent-core): message` and preserve the workspace until the lead integrates the committed handoff. Do not merge, deploy or change another service.

## Worktree and dependencies

Use `feat/agent-core-t05-runtime-foundation`, worktree label `agent-core-t05`; Git fallback `/tmp/shopops2026-agent-core/T05`. Start from the lead's committed spec/live-fix baseline. Publish a small verified foundation SHA before T06/T07/T08 code; continue storage/worker/API work after that gate. Final completion waits for their handoffs.

## File ownership

- Shared models/protocols: `app/contracts/{runtime,models,provider,repository}.py`, `contracts/managed-runtime.md`, `contracts/runtime-report.schema.json`.
- Runtime config and persistence: `app/config/{settings,registry}.py`, `config/registry.json`, new `config/registry-hosted.example.json`, `app/storage/{database,repositories}.py`, `app/storage/migrations/002.sql`.
- Wiring/API: `app/{composition,main}.py`, `app/runs/worker.py`, new `app/api/artifacts.py`, existing API router/schemas and `contracts/application-api*` exports.
- Shared settings/dependencies/docs: `.env.example`, README, Dockerfile only if bundle packaging needs it, central task table, dependency files and shared test doubles/conftest.
- Tests: `tests/runtime/test_contracts.py`, `tests/runtime/test_profiles.py`, `tests/storage/test_runtime_migration.py`, `tests/api/test_artifacts.py`, `tests/runs/test_hosted_recovery.py`.

T06 owns provider implementation; T07 owns bundle files and agent capability/instruction modules; T08 owns hosted acceptance scripts/tests. Publish stubs at the foundation gate, then transfer their module ownership explicitly.

## Interfaces

Consume unchanged `Scope`, AuthContext, existing Source/ToolResult and root-run receipt semantics. Produce the extension's runtime/bundle/environment/artifact models, optional profile normalization, artifact provider methods, and **fully typed async repository signatures** in `contracts/managed-runtime.md`. Freeze the report JSON schema before consumers implement scripts.

Preserve the existing response schema; add optional message output_mode=text|report (default text), persisted in Run and included in the idempotency hash; add artifact list/content routes with `history:read`, scope lookup and local artifact IDs. Source attribution must remain session/root-turn scoped. T06 environment progress maps to running/reconciling; child/command events never finalize a root run.

## Review focus

- Legacy DB/config records without runtime fields must remain `none` across activation/restart.
- Foreign artifact IDs and forged paths must be rejected before provider I/O.
- Restart between session creation and receipt persistence must not duplicate initial input.
- Child completion before the root must not unlock the conversation or publish its result.
- Failed remote cleanup must retain IDs and application cleanup state for recovery.

## Steps

- [ ] **1. Write foundation regressions.** Add contract/profile/migration tests. Assert legacy normalization to `conversation-v1`; pinned hosted digest survives DB reopen/activation; a changed digest/profile combination fails before provider calls; one exclusive DB owner is retained.
- [ ] **2. Verify RED.** Run `.venv/bin/pytest tests/runtime/test_contracts.py tests/runtime/test_profiles.py tests/storage/test_runtime_migration.py -v`; confirm failures identify missing runtime contracts/migration, not external prerequisites.
- [ ] **3. Publish the foundation.** Add closed shared models, report schema, exact async signatures, migration and consumer doubles. Validate SDK surfaces offline, coordinate any pin change, then rerun Step 2 plus `make lint`. Commit as `feat(agent-core): publish hosted runtime contracts`; record exact SHA in the central foundation gate and notify consumer owners. They start from this commit, not the reference baseline.
- [ ] **4. Write integration regressions.** In artifact API tests assert 404 for another tenant/shop/user with zero provider calls, safe attachment headers, bounded reads/digest checks, 410 unavailable, 502 invalid and 503 transient I/O. In worker tests assert setup deadline, root-only finalization, two-child event replays, required report missing/invalid, report-mode clarification/cannot_answer completing without artifacts, text-mode policy-only answers, output_mode replay/conflict and legacy rejection, and unknown-outcome blocking.
- [ ] **5. Verify RED, implement coordinator/API behavior.** Run `.venv/bin/pytest tests/api/test_artifacts.py tests/runs/test_hosted_recovery.py -v`, establish failures, then implement scoped metadata persistence, artifact finalization/download, runtime progress and recovery without another agent loop. Export matching application API contracts. Add RUNTIME_BUNDLE_PATH docs/settings with no secret defaults.
- [ ] **6. Integrate T06/T07/T08 committed handoffs.** Wire build_runtime_bundle/build_hosted_environment into the configured provider, include registered bundles in the image, and keep profile activation administrative. Preserve internal MCP transport and legacy `none` tests.
- [ ] **7. Verify delivery.** Run `make ci`, `make docker` and `.venv/bin/python -m scripts.verify_volume_restart`. Validate migration/profile/runtime/artifact metadata survive recreation; default CI makes no OpenAI requests. Accept AC15/AC19, supporting AC20/AC21 and T08's actual live evidence before marking the extension complete.
- [ ] **8. Commit handoff.** Use `feat(agent-core): integrate hosted runtime lifecycle`, audit changed paths against the base SHA, and record results/blockers. No live success is inferred from fakes or Docker alone.


## Handoff record

- Actual worktree / branch: not recorded.
- Base SHA / imported T05 foundation SHA: not recorded.
- Result commit SHA / changed-path audit: not recorded.
- Scoped test commands/results / relevant acceptance IDs: not recorded.
- Live evidence or exact missing prerequisite / unresolved integration issues: not recorded.

Update this description only for your handoff; the runtime integration lead updates the central task table. Mark Ready for integration after module verification, not Done until required integration evidence is accepted.
