# T08 Hosted Integration and Live Acceptance

> **For agentic workers:** Use `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` when delegation is selected. Track work with checkboxes.

**Goal:** Prove the hosted template works through the application API with actual skills, commands, two specialists, scoped artifacts and recoverable cleanup.

**Architecture:** Keep deterministic failure/authorization tests offline and put provider-dependent proof in a separately gated synthetic smoke. Evidence is aggregate and tied to actual saved OpenAI items/turns, not model wording.

**Tech Stack:** Python 3.14, FastAPI, SQLite, official OpenAI SDK, pytest, Docker and existing MCP transport.

**Spec:** [Managed runtime extension](../../agents_api_managed_runtime_spec.md), [main spec](../../agents_api_template_spec.md), [tracker](../task_list.md#hosted-runtime-extension-t05t08).

**Status:** Not started. **Difficulty:** D5 — Very hard. The test crosses application durability, provider provisioning, shared workspace, delegation, artifacts, secrets and teardown; partial success must remain visible.

## Global constraints

Read the root and service AGENTS.md, the main template spec, runtime extension spec, and the tracker's **Hosted runtime extension (T05–T08)** section first. All paths below are relative to `services/agent-core/`; root workflows/templates/scripts and other services are read-only. Use Python 3.14, pinned dependencies, Ruff line length 100, one SQLite owner/worker/replica and existing API scopes. Keep default CI offline except loopback. You are not alone in the codebase: preserve other owners' changes and import shared amendments from T05 rather than copying files.

Do not copy env files between worktrees or print credentials, prompts, model output, tool data or command output in logs/evidence. Existing `none` live evidence is not hosted acceptance. Work in the assigned separate worktree and keep a private venv/DB/evidence directory. Use commits `type(agent-core): message` and preserve the workspace until the lead integrates the committed handoff. Do not merge, deploy or change another service.

## Worktree and dependencies

Use `feat/agent-core-t08-hosted-acceptance`, label `agent-core-t08`; Git fallback `/tmp/shopops2026-agent-core/T08`. Start fixture/test preparation from the published T05 runtime foundation SHA. Final end-to-end work waits for T05 application wiring and committed T06/T07 handoffs; import reviewed commits through the lead.

## File ownership

- New `scripts/hosted_smoke.py`, `scripts/demo_live_hosted.py`.
- `tests/integration/test_hosted_workflow.py`, `tests/live/test_hosted_runtime.py`, `tests/runtime/test_hosted_live_gate.py`.
- Synthetic `fixtures/runtime/` inputs and `contracts/hosted-acceptance.md` runbook/evidence format.
- This task description's evidence record. Request shared pytest/network-guard changes from T05; do not edit existing baseline live smoke behavior or central README/tracker independently.

## Interfaces

Consume T05's runtime profile/artifact API/report schema and provider doubles, T06's hosted adapter, and T07's registered bundle/digest. Drive existing `/api/v1` provision/conversation/message/run/history endpoints plus scoped artifact list/content endpoints. No raw-provider-only demo can substitute for the integrated API flow.

Expose CLI `python -m scripts.demo_live_hosted --live --hosted --credentials-file <ignored-file> --evidence .evidence/live-hosted.json`. Require both explicit acknowledgements; reuse the existing key/model-only loader. Hosted pytest requires AGENT_CORE_LIVE=1 and AGENT_CORE_LIVE_HOSTED=1, independent of the baseline live test.

## Review focus

- Enabling legacy live alone must not accidentally create billable hosted sandboxes.
- A generated report or claimed specialist role without saved provider execution evidence must fail acceptance.
- A partial smoke failure must still attempt cleanup of every known session.
- Delete 409 and unknown cleanup outcomes must retain recovery state and fail the smoke.
- Restart, cross-scope downloads and workspace expiry must not silently replace sessions or leak artifacts.

## Steps

- [ ] **1. Write opt-in gate tests and verify RED.** Use subprocesses with sanitized env and fake request counters to assert zero provider calls for neither flag or either single flag. Assert the CLI rejects missing --live/--hosted before network. Run `.venv/bin/pytest tests/runtime/test_hosted_live_gate.py -v`.
- [ ] **2. Build failure fixtures and offline API tests.** In `test_hosted_workflow.py`, cover two child identities plus delayed root completion, bundle mismatch, setup failure/timeout, stream loss/reopen, environment expiry, foreign artifact access with zero remote calls, declared-size/digest mismatch, delete 409/404 and unknown cleanup. Assert baseline source schemas/history receipts stay intact. Establish RED before adding the smoke/test support.
- [ ] **3. Implement the bounded synthetic smoke.** First conversation explicitly sends output_mode=report and requests fixture metrics and policy evidence, actual skill/script execution, two specialist analyses and the canonical report. A text-mode follow-up must reuse its session without requiring another report. Add a report-mode missing-information case that completes as clarification without fabricated metrics/artifacts. A second conversation establishes distinct session/environment/artifact scope. Fetch reports through the application API and compare numbers/source IDs to fixtures, not exact generated prose.
- [ ] **4. Collect provider proof and cleanup.** Record runtime type, connected environment, successful command item, skill read/helper execution, at least two distinct child IDs/turns, root completion and artifact checks. All resource-producing calls enter cleanup tracking immediately. In finally stop local worker, cancel/reconcile active roots, clean all known sessions/artifacts independently, confirm session absence/cleanup request, then remove local state. If cleanup is unresolved, preserve recovery IDs/directory and fail the smoke. Do not claim physical sandbox destruction from accepted deletion.
- [ ] **5. Verify offline first.** Run `.venv/bin/pytest tests/runtime/test_hosted_live_gate.py tests/integration/test_hosted_workflow.py -v`, then `make ci`. Default CI must have no credentials/network beyond loopback and skip both live suites.
- [ ] **6. Run explicit hosted acceptance only when authorized and configured.** Use `AGENT_CORE_LIVE=1 AGENT_CORE_LIVE_HOSTED=1 .venv/bin/pytest tests/live/test_hosted_runtime.py -v`, with OPENAI_API_KEY/OPENAI_MODEL supplied through the process. The CLI may instead use the explicit ignored credentials file. Verify a harmless network-denial probe and absent backend-secret names without outputting values. Record account/model/SDK/bundle and all AC15–AC22 evidence or exact unavailable prerequisites.
- [ ] **7. Deliver reviewable evidence.** Keep aggregate JSON in ignored .evidence; store no keys, prompts, generated content, private URLs or raw command/inter-agent output in the commit. Use `test(agent-core): verify hosted runtime acceptance`; provide the lead verification results, cleanup outcome and remaining blockers. Real shop/JWT/CapRover onboarding is separate from synthetic acceptance.


## Handoff record

- Actual worktree / branch: not recorded.
- Base SHA / imported T05 foundation SHA: not recorded.
- Result commit SHA / changed-path audit: not recorded.
- Scoped test commands/results / relevant acceptance IDs: not recorded.
- Live evidence or exact missing prerequisite / unresolved integration issues: not recorded.

Update this description only for your handoff; the runtime integration lead updates the central task table. Mark Ready for integration after module verification, not Done until required integration evidence is accepted.
