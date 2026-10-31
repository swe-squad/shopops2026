# T08 Hosted Integration and Live Acceptance

> **For agentic workers:** Use `superpowers:executing-plans` for inline execution or `superpowers:subagent-driven-development` when delegation is selected. Track work with checkboxes.

**Goal:** Prove the hosted template works through the application API with actual skills, commands, two specialists, scoped artifacts and recoverable cleanup.

**Architecture:** Keep deterministic failure/authorization tests offline and put provider-dependent proof in a separately gated synthetic smoke. Evidence is aggregate and tied to actual saved OpenAI items/turns, not model wording.

**Tech Stack:** Python 3.14, FastAPI, SQLite, official OpenAI SDK, pytest, Docker and existing MCP transport.

**Spec:** [Managed runtime extension](../../agents_api_managed_runtime_spec.md), [main spec](../../agents_api_template_spec.md), [tracker](../task_list.md#hosted-runtime-extension-t05t08).

**Status:** Ready for integration (offline module only; hosted live acceptance remains UNVERIFIED). **Difficulty:** D5 — Very hard. The test crosses application durability, provider provisioning, shared workspace, delegation, artifacts, secrets and teardown; partial success must remain visible.

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

- [x] **1. Write opt-in gate tests and verify RED.** Use subprocesses with sanitized env and fake request counters to assert zero provider calls for neither flag or either single flag. Assert the CLI rejects missing --live/--hosted before network. Run `.venv/bin/pytest tests/runtime/test_hosted_live_gate.py -v`.
- [x] **2. Build failure fixtures and offline API tests.** In `test_hosted_workflow.py`, cover two child identities plus delayed root completion, bundle mismatch, setup failure/timeout, stream loss/reopen, environment expiry, foreign artifact access with zero remote calls, declared-size/digest mismatch, delete 409/404 and unknown cleanup. Assert baseline source schemas/history receipts stay intact. Establish RED before adding the smoke/test support.
- [x] **3. Implement the bounded synthetic smoke.** First conversation explicitly sends output_mode=report and requests fixture metrics and policy evidence, actual skill/script execution, two specialist analyses and the canonical report. A text-mode follow-up must reuse its session without requiring another report. Add a report-mode missing-information case that completes as clarification without fabricated metrics/artifacts. A second conversation establishes distinct session/environment/artifact scope. Fetch reports through the application API and compare numbers/source IDs to fixtures, not exact generated prose.
- [x] **4. Collect provider proof and cleanup.** Record runtime type, connected environment, successful command item, skill read/helper execution, at least two distinct child IDs/turns, root completion and artifact checks. All resource-producing calls enter cleanup tracking immediately. In finally stop local worker, cancel/reconcile active roots, clean all known sessions/artifacts independently, confirm session absence/cleanup request, then remove local state. If cleanup is unresolved, preserve recovery IDs/directory and fail the smoke. Do not claim physical sandbox destruction from accepted deletion.
- [x] **5. Verify offline first.** Run `.venv/bin/pytest tests/runtime/test_hosted_live_gate.py tests/integration/test_hosted_workflow.py -v`, then `make ci`. Default CI must have no credentials/network beyond loopback and skip both live suites.
- [ ] **6. Run explicit hosted acceptance only when authorized and configured.** Use `AGENT_CORE_LIVE=1 AGENT_CORE_LIVE_HOSTED=1 .venv/bin/pytest tests/live/test_hosted_runtime.py -v`, with OPENAI_API_KEY/OPENAI_MODEL supplied through the process. The CLI may instead use the explicit ignored credentials file. Verify a harmless network-denial probe and absent backend-secret names without outputting values. Record account/model/SDK/bundle and all AC15–AC22 evidence or exact unavailable prerequisites.
- [x] **7. Deliver reviewable evidence.** Keep aggregate JSON in ignored .evidence; store no keys, prompts, generated content, private URLs or raw command/inter-agent output in the commit. Use `test(agent-core): verify hosted runtime acceptance`; provide the lead verification results, cleanup outcome and remaining blockers. Real shop/JWT/CapRover onboarding is separate from synthetic acceptance.


## Handoff record

- Actual worktree: `/home/khalee-dev/.codex/worktrees/e1a8/shopops2026`; branch
  `feat/agent-core-t08-hosted-acceptance`. Native managed worktree retained for the lead.
- Starting foundation: `1e45865ce1e4a3cb2b2518740b0c51b9efe2f967`.
  Imported committed T05 lifecycle `ebd7537` / handoff `428e2c7`, T07 bundle `c955460` /
  handoff `944481f`, and T06 provider `dc05790` / handoff `6e122fc`.
  Local dependency-only base after imports: `d1dbe63`.
- Steps 1–5 and 7 are implementation/offline handoff checks only. They do not establish saved
  real hosted execution or AC16–AC22 live acceptance. Step 6 remains intentionally unchecked.
- Gate RED: eight missing-runner/CLI failures; evidence/cleanup RED: thirteen missing-helper
  failures. Subsequent adversarial RED cases reproduced heredoc/compound command false proof,
  two roles on one child, early worker shutdown, lost application receipt, recovery-file write
  failure, shutdown falsely returning passed, unapproved executable paths and invented child
  knowledge references. Every T08-owned fix was verified through regression tests.
- Independent read-only review found four actionable issues (recovery write blocking cleanup,
  shutdown false success, bundle provenance, child source provenance). All were reproduced
  offline and fixed. The helper now verifies registered bytes and executes exactly those bytes
  in one isolated hosted Python command; skill outputs match approved content; child references
  match successful ToolResults for the same session/root. No further review findings were deferred.
- Only T08-owned scripts, tests, fixtures, runbook and this description are changed after the
  dependency-only base. No central tracker, shared API mapping, README, Dockerfile, other
  service or root credentials were edited by T08. Dependency imports remain separate commits.
- `graphify update .` ran AST-only in the ignored service-local graph directory. SQL extraction
  is partial because `tree_sitter_sql` is not installed; no semantic/API extraction ran.
- Live: NOT RUN / UNVERIFIED. No billable OpenAI request, sandbox, real artifact or session was
  created; there is no live cleanup outcome to claim. The user requested the available offline
  work. A separately explicit hosted opt-in with operator key/model/account capability is still
  required, followed by actual saved evidence and confirmed cleanup.
- Integration dependency: T05 `app/api/runs.py:public_error` currently converts the three hosted
  environment error codes to `internal_error`. Three strict expected failures preserve that gap;
  they are not acceptance passes. Import the lead's safe-error amendment and remove the xfail
  marker after verifying the specified codes. Docker bundle packaging and any custom bundle-path
  wiring remain lead-owned final integration checks.
- Runbook/evidence/recovery contract: `contracts/hosted-acceptance.md`. Runtime/evidence files
  stay under ignored service-local `.evidence/`; no raw prompts/content/credentials are committed.

### Verification and result commit

- Final credential-free `make ci` on Python 3.14.7 / SDK 3.42.0: **393 passed,
  2 skipped, 3 xfailed**, exit 0; Ruff lint and format pass. The skipped tests are the
  explicitly gated legacy and hosted live suites; all three xfails are the T05 public errors
  named above and are not counted as acceptance passes.
- Scoped final command: `.venv/bin/pytest tests/runtime/test_hosted_live_gate.py
  tests/integration/test_hosted_workflow.py -v`: **47 passed, 3 xfailed**, exit 0.
- Four independent-review findings reproduced RED, then fixed; final full offline CI above
  verifies the fixes and regressions. Local hash-helper execution is synthetic test evidence,
  never a hosted command claim.
- Result implementation commit: `e6487284fdfa416abfc26731a25ef7138df65752`
  (`test(agent-core): verify hosted runtime acceptance`).
- Final `git diff --name-only d1dbe63...e648728` audit: exactly eight T08-owned files under
  `services/agent-core/` (two scripts, three test files, one fixture, one runbook, this description).
  `git diff --cached --check` passed before commit; implementation commit left the worktree clean.
- Branch/worktree are retained for the lead. No push, PR, merge or deploy was performed.



Update this description only for your handoff; the runtime integration lead updates the central task table. Mark Ready for integration after module verification, not Done until required integration evidence is accepted.


## Lead integration checkpoint

The user confirmed the module handoff complete. Implementation `e648728` and handoff `6894bfb`
were imported into `feat/agent-core-hosted-runtime` as `00d201d` / `e329467`; the original task
worktree and commits remain intact. The historical module results above are retained as recorded.

- `9562b46` resolves the T05 public-error dependency and removes all three strict xfails. It also
  requires positive artifact-delete acknowledgements while still attempting every other resource.
- `43d3abf` adds fixed workflow stages and safe run status/error diagnostics, with content-leak
  regression coverage. `7d2700d` fixes a live-observed command shape: saved system bash login-shell
  wrappers are unwrapped once, then the same exact inner proof checks apply. Two positive cases
  were RED before the fix; direct and wrapped adversarial cases remain rejected.
- Final integrated Python 3.14 / SDK 3.42.0 `make ci`: **428 passed, 2 live skipped, zero xfails**.
  Scoped T08 tests: **72 passed**. Docker build PASS; volume restart and runtime bundle packaging
  have recorded integration evidence. The new diagnostic/parser deltas received independent
  read-only review with no P0/P1 findings. Runtime/graph/evidence files remain ignored.
- Actual hosted attempts are separate from the original offline handoff. Connected sandbox,
  completed root, two child identities and completed commands have been observed, but complete
  saved-proof/artifact/follow-up/isolation acceptance is not inferred from those partial facts.
  The central tracker records the final attempt and cleanup outcome.

### Actual hosted result (lead)

Four bounded attempts used `gpt-6-astra`, SDK 3.42.0 and bundle `1.0.0`. Each created one known
session before the proof gate; all four confirmed session absence and local cleanup. No known
remote resource remains unresolved, and physical sandbox destruction is not claimed.

After the bash-wrapper fix, the final saved proof passed both approved skill reads and exact
verified-helper execution, then failed the fixed boundary-probe check. The root, two child turns
and nine commands completed, and two MCP calls succeeded without worker/MCP errors. Both child
`instructions` fields were null, while child assistant outputs were present; the current contract
cannot bind those outputs to the required assigned roles. No encrypted/absent task content is
inferred as plaintext. The fixed probe evidence and role binding remain UNVERIFIED.

The integrated workflow stops at that proof gate. Complete artifact download/numeric verification,
same-session follow-up, separate-conversation isolation and overall AC22 are NOT ACCEPTED.
Step 6 remains unchecked. The integration is prepared for draft review; no further paid run,
contract relaxation, merge or deployment is implied. Aggregate evidence stays in ignored
`.evidence/live-hosted-attempt1.json` through `.evidence/live-hosted-attempt4.json`.
