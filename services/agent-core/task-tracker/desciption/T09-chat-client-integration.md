# T09 Chat Client to Agent Core Integration Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when delegation is explicitly selected. Track implementation steps with checkboxes. Task creation does not start implementation or authorize live calls/deployment.

**Goal:** Let the existing ShopOps chat UI use Agent Core's hosted conversations, tools, skills, specialists and report artifacts through its existing chat backend.

**Architecture:** `shopops-chat → shopops-chat-api → agent-core → OpenAI Agents API`. The chat API is an HTTP adapter for the one phone-number demo user and one configured shop; Agent Core owns provider execution and canonical conversation history. Preserve the standalone clients and the presentation-only workspace viewer.

**Tech Stack:** Existing React/TypeScript/Vite client, Python 3.14/FastAPI, SQLite, pinned httpx, pytest, Vitest and shared Docker/CapRover delivery.

**Spec:** [Integration design](#integration-design) below, [application API](../../contracts/application-api.md), [managed runtime](../../agents_api_managed_runtime_spec.md), [client architecture](../../../../docs/client-workspace.md), [tracker](../task_list.md#chat-client-integration-follow-up-t09).

**Status:** Ready for integration — T09-R01/R02 fixed and verified offline; hosted acceptance remains UNVERIFIED. **Difficulty:** D5 — Very hard. The work crosses one phone demo identity, scoped resource access, durable HTTP submission/recovery, polling-to-SSE adaptation, two independent databases, scoped downloads and legacy compatibility. A successful browser reply alone does not prove hosted execution.

## User scope amendment: one user and one shop

The current deliverable is exactly **one demo phone number → one owner → one configured shop → one logical shop orchestrator**. Login has no OTP. Multi-user login, two users provisioning the same shop, additional user/shop registration and new privileged Core demo identities are out of scope. This supersedes the earlier two-user fixture requirement and the proposed additional provisioning-fixture approval.

On the first successful demo login, idempotently provision or retrieve the configured shop orchestrator using the existing `local-alice` fixture. Persist that mapping before completing initialization. Re-login/provisioning replay must return the same orchestrator; it must not create another shop or grant permissions. This is application metadata only: create/reuse the conversation and let Core create its OpenAI session/environment when the first message executes. A login alone must not start a billable agent run. Keep existing negative authorization/scope tests; they do not require implementing a second login identity.

## Baseline, dependencies and worktree

- Start from committed `develop` containing PR #8; planning baseline `53d094e`. Record the actual starting SHA and any later reviewed amendments before coding.
- T05–T08 code is merged. Offline adapter/UI work can start now. T08's exact boundary-probe evidence and child-role binding remain unaccepted; T09 must not fix them by weakening the proof contract or claim that merge established live acceptance.
- Real hosted acceptance additionally needs an accepted hosted registry revision, operator credentials and the server-owned demo identity mappings. Real shop ingestion and production identity onboarding are separate work.
- Branch `feat/shopops-chat-agent-core`, native worktree label `shopops-chat-agent-core`; Git fallback `/tmp/shopops2026-agent-core/T09`. Create/reuse only a matching isolated implementation workspace. The current documentation worktree is not an implementation handoff.
- One integration owner coordinates the phone-login/backend/client contract. Do not let parallel workers edit shared schemas/store/controller files without explicit ownership. Preserve other agents' changes and all T08 evidence/worktrees.

## Scope and file ownership

All paths here are repository-root relative. This is a proposed follow-up scope for the later implementation request; the previous agent-core-only boundary remains applicable to T01–T08.

| Area | Owned paths and responsibility |
| --- | --- |
| Chat backend | Create `services/shopops-chat-api/app/agent_core.py` for the HTTP boundary, `app/core_chat.py` for run coordination, `app/demo_auth.py` for phone demo sessions, `app/navigation.py` for the authenticated operations mailbox adapter and `fixtures/demo-identities.json` for one server-owned synthetic identity; update its existing `app/main.py`, `settings.py`, `contracts.py`, `store.py`, `.env.example` and README for explicit selection, migrations and API composition |
| Backend verification | Create `services/shopops-chat-api/tests/test_agent_core_contract.py`, `test_agent_core_recovery.py`, `test_agent_core_artifacts.py`, `test_agent_core_integration.py`, `test_demo_phone_auth.py`, `test_agent_core_navigation.py`; preserve the existing direct-provider regressions |
| Chat client | Update `services/shopops-chat/src/App.tsx`, `App.test.tsx`, `workspace-api.ts`, `use-chat-controller.ts`, `chat-client.tsx` and their existing tests; add focused artifact-download UI/tests and minimal styles inside this service |
| Core integration support | Service-local loopback fixture support/tests, operator configuration documentation and this tracker under `services/agent-core/`; existing public `/api/v1` contracts remain the boundary |

Read root and all three service AGENTS.md files first. Before UI changes read the canonical brand/design guidance. Keep Python 3.14, pinned dependencies, current Makefile targets and each service's private environment. No shared Python imports, direct access to another service's DB, root workflow changes, shop browser/viewer state changes, UI redesign, production authentication service, OTP integration or direct sandbox-to-cluster connectivity.

## Integration design

### Selected approach and ownership

Use the existing chat API as the browser-facing adapter. Calling Agent Core directly from the browser would change authentication/proxy boundaries; importing its worker/provider into the chat service would create a second execution owner. Neither is part of this task.

The user selected **phone-number login for a demo, without OTP**. Implement this as an explicitly labelled demo identity flow using server-owned synthetic phone fixtures; it is not verified phone ownership or production authentication. Do not add SMS/OTP or claim that a number was verified.

Add explicit `CHAT_BACKEND=openai_agents|agent_core`, defaulting to the existing direct-provider mode for compatibility. When `agent_core` is selected, missing configuration fails startup; there is no fallback to direct OpenAI, `none` or fake execution. That mode must work without an OpenAI key or saved-agent ID in the chat API and must make zero direct provider calls.

Agent Core remains responsible for its `openai_agents` provider, explicit model, hosted registry revision, approved bundle, private MCP bridge, root/child reconciliation and artifact validation. An environment variable on the chat service does not activate a core revision. The operator must configure/activate the intended immutable hosted revision for new conversations; preserve existing pinned conversations and surface configuration conflicts.

### Configuration and phone-number demo identity

The user explicitly chose phone-number entry **without OTP** for the demo. Add:

- `CHAT_AUTH_MODE=workspace_token|demo_phone`; preserve workspace-token auth for the legacy backend. The new Core demo flow uses `demo_phone`.
- `APP_ENV=local|test` for demo auth, matching Core's fixture boundary. Refuse demo-phone mode in other environments; do not loosen Core's existing JWT/fixture restrictions.
- `AGENT_CORE_URL`: required trusted base URL in core mode; `.env.example` uses `http://127.0.0.1:8002`. CapRover's future internal URL is operator-supplied, never a hardcoded/dev default or public-service URL.
- `AGENT_CORE_SHOP_ID` and `AGENT_CORE_CONFIG_REVISION`: required configured values. Template `shopops` is the existing template.
- `SHOPOPS_API_URL`: operations mailbox base URL, localhost example `http://127.0.0.1:8000`. `SHOP_API_TOKEN` stays server-side for that existing single-workspace API and legacy mode; it is not the phone user's browser credential.

Phone numbers are strings, normalized to an explicit international `+` country-code format (8–15 digits). Never use numeric types, invent a country code, or accept phone/tenant/user headers as authorization. The new UI asks for a demo phone number and has no OTP screen. Public auth configuration reveals only the login mode, not credentials or internal URLs.

Create exactly one positive synthetic phone-to-identity mapping in the chat API fixture: the configured demo phone maps to Core's existing `local-alice` identity (`tenant-a`, `alice`) and selected `shop-a`. Restrict the adapter to `shop-a` even though the existing Core fixture has another shop membership. `local-alice` already has `orchestrator:provision`, `conversation:write` and `history:read`; no new Core identity or permission expansion is needed. Keep `local-bob`, `local-carol` and all existing Core fixtures unchanged. Unknown phones fail; do not auto-enrol another phone/shop or derive access rights from a typed number. The normalized phone is the unique demo login identifier; Core continues using its existing opaque `user_id`/`sub` identity contract. Foreign identities/resources may be used as negative test inputs only; a second functioning demo login is outside this task.

Expose `GET /api/chat/auth/config`, `POST /api/chat/auth/demo-phone` with `{phone_number}`, and authenticated `POST /api/chat/auth/logout`. Login returns a random opaque `access_token` and `expires_at`, valid for one hour. Store only the token hash and mapped identity/expiry server-side. The browser keeps the token in memory and clears it on lock/reload; re-entering the same demo phone restores the same mapped user's durable conversation. Logout revokes that session. No phone numbers, tokens, prompts or identity claims belong in logs/URLs/errors.

Authenticate every chat/history/capability/download/navigation request from that session. Select the configured shop only if the mapped identity is a member; enforce tenant/user/shop scope on every DB lookup and Core call. Resolve the configured demo owner's Core fixture credential on the server; do not forward the demo access token or the phone number as Core authorization. Browser input cannot select tenant, user, permissions or an upstream token. Foreign or unmapped resources must return 404 without upstream artifact reads. Real per-phone ownership verification/JWT onboarding remains outside this demo task.

Construct Core routes from validated application IDs against the configured base URL; never follow arbitrary `polling_url` values or cross-origin redirects. Validate settings before I/O. The chat API makes no direct OpenAI requests and needs no OpenAI key in core mode. Separately gated hosted smoke may use Core's existing local fixture auth with synthetic data; this does not establish production identity acceptance.

### Existing shop-browser navigation

The operations API still accepts its workspace token. A phone session must not be sent to it as that credential. Add authenticated `POST /api/chat/navigation` with the existing `{url}` shape; the chat backend checks the mapped shop membership and forwards only the allowed navigation payload to the configured operations mailbox using its server-held token. Update the chat UI to use this adapter after phone login. Preserve origin-relative `/shop/...` links and navigation-only retries. The independently hosted browser remains unchanged and unlocks through its existing mechanism; this task does not migrate the operations API's identity model. Report downloads must never enter this mailbox.

### HTTP and browser contract

Consume these existing Core routes under `/api/v1` using the configured demo owner's server-resolved Core fixture credential:

| Purpose | Core route / mapping |
| --- | --- |
| Provision | `POST /shops/{shop_id}/orchestrator` with `template_id=shopops`, configured `config_revision` |
| Conversation | `POST /shops/{shop_id}/conversations` with saved `orchestrator_id` and durable `client_conversation_id` |
| Submit | `POST /conversations/{id}/messages` with durable `client_message_id`, `content`, `output_mode`; save its 202 `message_id`/`run_id` before polling |
| Outcome | `GET /runs/{id}`; only `completed` with a validated application response permits a browser `done`; `failed`/`cancelled` produce an error |
| History | `GET /conversations/{id}/history`, following validated cursors, preserving chronological order and projecting the latest 100 messages |
| Artifacts | `GET /runs/{id}/artifacts` and `GET /artifacts/{id}/content`, subject to the additional adapter scope checks below |

Keep browser `GET/POST /api/chat/messages` and SSE events `delta`, `done`, `error`. Extend message input with optional `output_mode=text|report` (default text) and `client_message_id`; the updated client supplies a UUID per send action. Preserve the existing 2000-character, non-whitespace text limit. Reject conflicting replay payloads and browser-supplied shop/tenant/actor/provider configuration.

Add authenticated `GET /api/chat/capabilities` returning only `{report_mode: bool, artifacts: bool}`. Both are false in legacy mode and true only for the configured core integration. The UI shows report/download controls only when supported; a legacy-mode report request returns 422 before provider I/O. No provider/model/identity settings are returned by this route.

Core history provides application message UUIDs and plain `content`. Map them to browser `id`/`text`, preserving role/time; widen backend `Message.id` to `int | str`, which the current client already supports. Legacy IDs remain integers. Add optional assistant `kind` (`answer|clarification|cannot_answer`), `sources` (`{type, reference}` using the existing Core source types), and at most two `artifacts` (`{id, filename, media_type, size, sha256, availability}` from the Core public artifact schema); derive them from authoritative run/artifact responses, not parsing generated prose. Download paths are constructed locally, not supplied as upstream URLs. Validate these additions in frontend transport/history parsing and document them in OpenAPI. Bound a history synchronization to 100 pages and 30 seconds; reject repeated/malformed cursors or a nonterminal page at the cap with a sanitized recoverable error. Never replace displayed history with an invented empty result on synchronization failure.

Core currently exposes polling/status events rather than model text deltas. Use a 10-second HTTP request timeout, a 260-second total polling budget, 0.5–2-second polling backoff and SSE comment heartbeats every 10 seconds; on timeout keep the pending mapping for explicit recovery; emit authoritative text at completion followed by `done`. Never fabricate incremental model tokens, completion, child-role success or tool output. Treat `clarification`/`cannot_answer` as valid completed application responses. Preserve the UI's honest waiting, Markdown, navigation and explicit history-recovery behavior.

There is no public Core cancellation endpoint. Browser Stop/disconnect stops viewing, closes adapter polling and leaves a durable pending run; it must not claim confirmed agent cancellation or call OpenAI directly. Recovery/history inspection determines completion before allowing another turn. Explain this behavior in UI copy and operator docs; a new Core cancellation API would require a separately reviewed contract change.

### Durability, replay and cutover

Agent Core is the canonical business history/execution owner. The chat database stores adapter correlation/outbox state, not a second provider session or independently generated assistant history. Persist phone-mapped tenant/user/shop/conversation keys, client-message ID, exact payload/mode fingerprint, accepted Core run/message IDs and pending status before each relevant network boundary. Use the existing SQLite lease/transactions to serialize submissions across workers sharing that chat DB.

An uncertain Core application POST may be replayed only with the same persisted idempotency key and identical body to recover its receipt under the existing idempotent API contract. This is not a new provider input. Never generate a replacement key/conversation after a timeout, duplicate a completed reply on replay, or infer success from EOF/idle/progress. Restart, lease loss and a crash between 202 and local commit must reconcile existing work. A replayed client ID with changed text or mode returns 409.

Keep existing direct-provider tables/history intact. Bind core correlations/history and the submission lease to the single configured backend, upstream base URL, tenant/user, shop and revision; keep the Core mapping separate from the legacy `workspace(id=1)` provider-session state and do not add a multi-user coordinator; a new core-mode conversation must not adopt a legacy provider session ID or present old direct-provider chat as its model context. Block mode/scope cutover while the previous namespace has unresolved work. Preserve an operator rollback path and verify migration/restart against a legacy database. Core has one SQLite owner/worker/replica; do not share its DB volume with the chat service.

### Reports and downloads

Add a small text/report choice and authenticated attachment control to the existing chat UI. No provider IDs, runtime settings or infrastructure labels belong in this flow. A report answer lists the validated root report; clarification/cannot_answer requires no attachment. Keep plain text mode and existing operations-link navigation intact.

Expose `GET /api/chat/artifacts/{artifact_id}/content` on the chat API, protected by the current demo phone session (or legacy auth only when explicitly supported). Before any Core artifact read, require a known artifact/run in the currently authenticated tenant/user/shop and mapped conversation. Reject foreign, unmapped or old-namespace IDs with 404 and zero upstream content calls. Resolve the actual download only through the configured Core base URL; do not accept upstream URLs/paths from the browser.

Forward bounded content and safe attachment/nosniff headers; enforce the current canonical report limit of 1 MiB. Never redirect to a provider URL or put tokens in an href. The frontend fetches with its in-memory token, downloads a Blob and revokes the object URL. Attachment downloads bypass the operations navigation mailbox. Expired content (410) leaves history intact and offers an honest unavailable state; transient download retry never submits another chat turn.

## Review focus

- Wrong/expired demo session, a typed phone/scope override or foreign artifact must not gain access or expose secrets.
- Lost receipts, restart, concurrent submissions and replay after completion must not create another Core input or conversation.
- Stop, EOF and `reconciling` must not become success or falsely claim remote cancellation.
- Backend/scope switching must preserve legacy rows and avoid mixing histories or adopting provider IDs.
- Missing report metadata, expired/malformed/oversize content and interrupted UI requests must not corrupt the reply or navigate/download with credentials in a URL.

## Implementation steps

- [x] **1. Freeze phone auth and adapter tests before implementation.** Add RED cases in `test_agent_core_contract.py` for settings/auth isolation, provision/conversation/message bodies, 202 receipts, terminal response kinds, polling/SSE comments, paginated chronological history, malformed/repeated cursor limits and zero direct OpenAI calls. Pin the additive browser input/output and authenticated capability contract in backend OpenAPI and `src/workspace-api.test.ts`; cover disabled report controls and rejected report input in legacy mode.
- [x] **2. Implement demo phone sessions and the HTTP boundary.** First add RED→GREEN cases in `test_demo_phone_auth.py` for international-number normalization, the one phone-to-owner/shop mapping, provisioning/replay with `local-alice`, unknown phone, expiry/logout, scope override and non-local demo rejection. Implement `app/demo_auth.py`, the login form and auth routes without OTP. Add typed validated Core request/response models and bounded HTTP operations in `app/agent_core.py`; select the adapter in settings/main while retaining the current provider's independent regressions. Missing core-mode config must fail before I/O. Verify all step-1 tests GREEN, then commit `feat(shopops-chat-api): add agent core HTTP adapter`.
- [x] **3. Implement durable coordination and migration.** Add correlation/outbox persistence and `app/core_chat.py`. In `test_agent_core_recovery.py`, reproduce lost provision/conversation/202 receipts, exact replay, conflicting replay, crash/reopen, lease loss, concurrent sends and cutover with legacy pending work, expired/revoked sessions and re-login/restart restoring the same owner/shop conversation. Make them GREEN without duplicate upstream logical input or destructive legacy migration; commit the recovery change.
- [x] **4. Add report projection and scoped downloads.** Write RED tests in `test_agent_core_artifacts.py` for valid report, clarification/no artifact, foreign/unmapped IDs with zero remote reads, 410, redirects/path injection, unsafe filenames/media, oversize/streamed content and secret-free errors. Implement metadata projection and authenticated proxying; verify GREEN before committing.
- [x] **5. Connect the existing UI and navigation.** Add RED→GREEN cases in `test_agent_core_navigation.py` for authenticated phone sessions, membership denial, server-only operations credentials and navigation-only retry. Implement the bounded mailbox adapter. Update controller/transport to send the stable client-message ID and selected output mode. Add focused tests for phone login/lock, report/text, final replacement, Stop/reload, UUID history IDs, malformed optional metadata, authenticated Blob download/revocation, expired attachment and no operations-navigation call for downloads. Preserve mobile layout, safe rendering and standalone/viewer isolation; run the existing UI suite and build.
- [x] **6. Prove the application boundary offline.** `test_agent_core_integration.py` must exercise a real loopback Core application with its own SQLite and explicit fake provider plus the chat API, not only a mocked HTTP transport. Add service-local Core fixture support if needed; run the services in separate processes/import environments to avoid their `app` package collision. Verify text, report, clarification, same-conversation follow-up, replay, restart, history and authorized/foreign downloads. Assert no external calls; synthetic artifacts/children remain explicitly fake evidence.
- [x] **7. Record configuration and deployment prerequisites.** Update owned `.env.example`/READMEs with demo-phone session/fixture separation, hosted revision activation, separate volumes, stop/cutover behavior and runtime cluster URL. Local ports: operations 8000, chat API 8001, Core 8002, client 5174. Existing container ports and public same-origin proxies remain unchanged.
- [x] **8. Verify and hand off.** Run the commands below, review service scope and preserve the isolated worktree. Record exact commits, changed paths, RED→GREEN/scoped/full results, migration/restart and image evidence. Run paid hosted acceptance only with a separately explicit opt-in, operator configuration and accepted T08 proof prerequisites; otherwise record it UNVERIFIED. Mark Ready for integration after module checks; Done requires accepted integrated evidence.

## Verification and acceptance

Run from each service directory with both `AGENT_CORE_LIVE` and `AGENT_CORE_LIVE_HOSTED` unset.
Independent chat API CI skips the separate cross-service test to avoid depending on another
service's private environment. After installing Core's private dependencies, explicitly run
`AGENT_CORE_LOOPBACK=1 .venv/bin/pytest tests/test_agent_core_integration.py -v` from the chat API.
This is offline loopback acceptance, not a paid/live flag:


- `services/shopops-chat-api`: `.venv/bin/pytest tests/test_demo_phone_auth.py tests/test_agent_core_navigation.py tests/test_agent_core_contract.py tests/test_agent_core_recovery.py tests/test_agent_core_artifacts.py tests/test_agent_core_integration.py -v`, then `make ci`.
- `services/shopops-chat`: `npm test`, then `make ci` for its independent lint/test/build.
- `services/agent-core`: `make ci` plus its existing hosted recovery/artifact regression suites if fixture/API-support files change.
- Build both changed chat images; record browser desktop/mobile and independent app checks. Record persisted adapter/core mappings after service restart using separate storage. A build alone is not persistence evidence.

Acceptance requires the existing chat UI to log in as the single configured demo phone without OTP, bind only its configured owner/shop, then complete text/report/clarification through the Core API, reuse its mapped conversation, display canonical history without duplicates, download only scoped validated artifacts, survive interruption/restart without new logical inputs, and keep legacy mode usable. In core mode the chat service requires no OpenAI key and makes zero provider calls. Offline results never establish real skill/specialist execution.

For actual hosted proof, reuse the established T08 credentials-loader/dual-opt-in policy with synthetic data; credentials remain at their original ignored location and are never copied between worktrees. Record aggregate model/runtime/bundle/turn/artifact/isolation/cleanup evidence only. Missing hosted account/settings or the two existing T08 proof gates remain explicit blockers for full acceptance. Do not merge, comment `/deploy`, deploy or leave billable sessions running as a documentation/implementation verification shortcut.

## Handoff record

- Historical implementation handoff at `7ee2b35`: **Ready for integration** for the offline module.
  The independent review below supersedes that readiness and reopens step 8. Full hosted acceptance
  remains **UNVERIFIED**; T08's exact boundary probe and child-role evidence remain unaccepted.
- Worktree: `/tmp/shopops2026-agent-core/T09`; branch `feat/shopops-chat-agent-core`.
  Base `fd3be2f5517518a9e65474394e9839c449385131` contains `develop` baseline `53d094e`.
  Applied the single-owner task amendment documented in `479c27f` without changing Core identities.
- Result commits: backend `0f32e6e`; frontend `ba5f3eb`; Core loopback support and this handoff
  are recorded in the following `test(agent-core)` commit.
- Changed paths: only `services/shopops-chat-api/` (HTTP/auth/navigation/outbox/artifact adapter,
  synthetic phone fixture, six targeted test modules, packaging/config/docs),
  `services/shopops-chat/` (phone UI, capabilities, UUID/mode transport, Blob downloads, tests,
  minimal styles/docs/ignore rules), and `services/agent-core/` (test-only loopback app, docs/tracker).
  Existing Core fixtures/permissions and browser/viewer clients are unchanged.
- Python 3.14.7 chat API `make ci`: **93 passed, 1 skipped** (separate loopback acceptance),
  Ruff check/format passed. Existing direct-provider regressions remain enabled.
- Explicit `AGENT_CORE_LOOPBACK=1 .venv/bin/pytest tests/test_agent_core_integration.py -q`:
  **1 passed**. A separate Core process uses its real application/worker and independent SQLite,
  with explicit synthetic provider/tools and external network blocked. Verified report, follow-up,
  clarification, completed replay, canonical six-message history, authorized/foreign downloads,
  re-login, chat restart, then Core restart with persistent history/artifact mappings. Foreign
  `local-bob`/`local-carol` reads remain denied. No new logical provider input after restart/replay.
- Frontend `make ci`: **48 passed**, lint and production build passed. The final build was also
  checked in headless Chromium at 1280×800 and 390×844 with synthetic API responses: one scroll
  log, visible composer, no horizontal overflow/page errors; report UUID/mode send, authenticated
  Blob download and separate navigation each occurred once. Standalone/viewer source was preserved.
- Core `make ci`: **428 passed, 2 skipped** (existing opt-in live gates); no live flag enabled.
- Both final chat Docker images built. Two network-isolated API image runs against the same
  task-only persistent directory preserve the one orchestrator mapping/client key. First login
  provisions once; recreation/re-login does not reprovision, create a conversation or run.
- Observed RED→GREEN evidence: initial settings/auth/Core contract, first-login provisioning,
  malformed frontend metadata and UUID/mode transport, sanitized request errors, pending-Core
  rollback refusal, permitted navigation compatibility, missing report artifact, and accelerated
  lease-expiry regression. Other added regression cases passed verification; no unobserved RED
  result is claimed for them.
- Read-only final review identified a P1 lease expiry during long finalization. Fixed by projecting
  only the current run, independently renewing the lease/emitting SSE comments, and bounding whole
  history reconciliation/replay. Accelerated clock regression fails without renewal and passes with
  it; the full backend suite is green. No findings were deferred in that implementation review;
  the subsequent independent review below identifies two additional open P1 issues.
- Graphify AST updates ran in each changed service. Generated graphs/evidence are service-local
  and ignored; Core SQL extraction is partial because `tree_sitter_sql` is unavailable.
- Environment note: the initial Python3.13 venv was replaced operationally by the service-local
  Python3.14 interpreter for canonical verification. Runtime Docker uses Python3.14. No root
  dependency files, workflows or unrelated workspaces were modified.

### Implementation rulings

- The user's single-owner amendment supersedes the earlier proposed extra demo identities.
  Exactly `+15550000001` maps to existing `local-alice` restricted here to `shop-a`; Core fixtures
  were restored unchanged. There is no permission expansion or second supported phone login.
- Cross-service loopback acceptance is a separate explicit offline opt-in so independent chat API
  CI does not silently require the sibling Core environment. Cost: maintainers must run the
  documented acceptance command in addition to standalone CI. Its actual result is recorded above.

Paid hosted end-to-end acceptance and remote cleanup proof remain **UNVERIFIED**, pending the
stated operator configuration/explicit opt-ins/T08 gates. No paid provider call, merge or deployment
was performed. This handoff preserves the isolated implementation branch/worktree.


## Independent review of 7ee2b35

**Current offline decision:** Both findings below are resolved by the follow-up fixes and fresh verification recorded below. Hosted acceptance remains a separate unverified gate.
The original review recorded these failures without changing product code; the following correction record documents the fixes. No paid/live call was added.

### T09-R01 — P1: explicit message rejection leaves the outbox pending

- **Location:** `services/shopops-chat-api/app/core_chat.py:86–91`, `CoreChat.receipt()`.
- **Trigger:** Configure the real Core fixture application with valid legacy revision `returns-v1`
  (`environment=none`), log in, and submit `output_mode=report`. Core rejects the input with 422.
- **Observed:** The first browser request receives an SSE error, but `core_outbox` remains `pending`
  with `run_id=NULL`. Loading history replays the same rejected report and returns 422. A corrected
  text message with a new client ID returns 409, and backend/scope cutover is also blocked. Core
  accepted no run, yet the adapter cannot recover without manual database intervention.
- **Required correction:** Distinguish a definite rejected application POST from an unknown outcome.
  Finish the locally rejected outbox entry without fabricating an assistant reply or `done` event.
  Preserve pending state for timeouts/unknown outcomes and preserve busy/idempotency-conflict semantics.
- [x] Add a regression proving 422 rejection releases the failed submission, history recovers and
  a corrected text submission can proceed without duplicate Core input.
- [x] Retain passing lost-receipt, timeout/unknown-outcome and replay regressions.
- [x] Record the fix commit and fresh scoped/full verification before closing T09-R01.

### T09-R02 — P1: cached orchestrator can create a conversation under another revision

- **Location:** `services/shopops-chat-api/app/core_chat.py:48–50`, `CoreChat.provision()`, and
  lines 65–76, `CoreChat.ensure()`.
- **Trigger:** Log in while `AGENT_CORE_CONFIG_REVISION=returns-hosted-v1`. Before sending the
  first message, activate `returns-hosted-v2` for the same shop in Core, then log in/send again.
- **Observed:** Cached orchestrator state skips provisioning validation. Core creates the new
  conversation using active v2 and the browser receives `done`, although adapter settings and its
  namespace still identify v1. The actual runtime/model/tool configuration may therefore differ
  from the selected immutable revision without a conflict being surfaced.
- **Required correction:** Bind or verify the intended revision at conversation creation and
  reject a mismatch without silently adopting it. Preserve existing pinned conversations and
  exact replay of an already-created conversation. Coordinate any necessary public Core contract
  amendment; a separate preflight must not be treated as an atomic revision guarantee.
- [x] Add a regression that activates a different revision between login and first message;
  the adapter must not complete under an unexpected revision or label it as v1.
- [x] Retain same-revision login/replay and existing-conversation revision-pinning coverage.
- [x] Record the fix commit and fresh scoped/full verification before closing T09-R02.

### Fresh verification at the reviewed commit

- Chat API `make ci`: **93 passed, 1 skipped** (explicit cross-service loopback gate).
- Chat client `make ci`: **48 passed**, lint and production build pass.
- Core `make ci`: **428 passed, 2 skipped** (the existing paid/live suites).
- Explicit `AGENT_CORE_LOOPBACK=1 .venv/bin/python -m pytest tests/test_agent_core_integration.py -q`:
  **1 passed**, with the real Core application/worker/SQLite and a synthetic provider.
- Both newly reported failure scenarios were independently reproduced offline with real Core
  HTTP/repository behavior. Existing green suites do not cover these two cases.
- Hosted acceptance/T08 probe and child-role proof remain separately UNVERIFIED; this review does
  not replace those gates. Product files remained unchanged during review.


## Review corrections after d3f2602

Both T09-R01 and T09-R02 are **resolved offline**. Task status is Ready for integration;
full hosted acceptance and T08 proof gates remain UNVERIFIED, so no merge/deployment is claimed.

- Core amendment: `311aa4e` (`fix(agent-core): guard conversation creation revision atomically`).
  Optional `expected_config_revision` is checked inside the same SQLite write transaction as
  snapshot selection/insertion. Existing scoped-key replay is checked first against the pinned
  snapshot; activation cannot silently change a replay, and different expectations conflict.
  Legacy clients omitting the field retain their old behavior. API/schema/protocol/OpenAPI and
  the application spec document this compatible addition. Deploy amended Core before the adapter.
- Adapter/outbox fix: `e34056f` (`fix(shopops-chat-api): preserve rejected and uncertain input outcomes`).
  A fresh definite application rejection records a failed local entry without assistant/done.
  Corrected input with a new key can proceed after canonical history recovery. Busy, idempotency,
  unknown conflicts, transport errors and uncertain receipts remain pending. Error text is sanitized.
- Review of the initial fix found that rejection during replay could not establish the outcome
  of an earlier lost202. A durable `message_dispatched` marker now precedes every message POST;
  later4xx cannot clear an earlier unknown outcome or permit unsafe cutover. Old tables migrate
  conservatively with existing rows treated as possibly dispatched; new entries start unsubmitted.
  This is a service-local migration; Core fixtures/permissions and legacy rows are preserved.
- Observed RED→GREEN: original403/404/422 stuck outbox, missing expected revision at adapter/API/
  repository boundaries, lost accepted receipt followed by401/403/422, and old outbox migration.
  Exact lost receipts, changed-payload conflicts, busy states, unknown outcomes and lease tests pass.
- Fresh Python3.14 chat API `make ci`: **104 passed, 4 skipped** (the separate loopback tests),
  Ruff/format passed. Explicit scoped run with `AGENT_CORE_LOOPBACK=1` and both paid/live flags
  unset: **33 passed**, including all four real-Core loopback cases.
- Real loopback cases: original report/history/restart; legacy Core report422 then corrected text;
  activation between login and first message rejects mismatched revision without any provider
  session, followed by explicit operator cutover; lost conversation receipt followed by activation
  replays the same pinned conversation and preserves its follow-up. No new logical input on replay.
- Fresh Core `make ci`: **431 passed, 2 skipped** (existing live gates), Ruff/format passed.
  Real repository/API tests include activation immediately before the create transaction, pinned
  replay after activation, changed-expectation conflict and compatibility with unguarded clients.
- Corrected Core and chat API Docker images build. With networking disabled, the API image migrates
  the previous task-only database and preserves its orchestrator/client key; the Core image enforces
  revision mismatch rejection and pinned replay. Frontend source is unchanged by these corrections;
  its existing48-test/build/browser evidence remains the previous baseline, not a new run.
- AST graphs updated in both changed services; ignored generated evidence remains service-local.
  Core SQL extraction remains partial without `tree_sitter_sql`. Only agent-core/shopops-chat-api
  source, tests, contracts and documentation changed; no paid call, permission expansion or deploy.
