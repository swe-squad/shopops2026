# agent-core

Hosted runtime roadmap: [Managed Codex Harness / OpenAI-hosted extension spec](agents_api_managed_runtime_spec.md), [T05–T08 task tracker](task-tracker/task_list.md#hosted-runtime-extension-t05t08). T05–T08 modules are integrated offline for hosted sandbox execution, approved skills, delegation and scoped artifacts. End-to-end hosted acceptance is tracked separately by T08; the original live smoke verifies the `none` conversation/tool profile.

FastAPI/Python 3.14 foundation for a durable, scoped ShopOps agent service on port 8000.
T01 supplies contracts, configuration, SQLite storage, scheduling/recovery, lifecycle and packaging.
T02 supplies auth/API routes, T03 supplies fake/live Agents API adapters, and T04 supplies MCP/tools.
All four module branches are integrated for offline execution. Default startup mounts the scoped
MCP apps and configures their bridge with the shared repository. Local/test fake-provider mode and configured live-provider mode can be ready. The live
provider now supports atomic session creation with initial input and has passed synthetic AC13.

## Intended product role

`agent-core` is the reusable **agents-service boilerplate**: team configuration, managed-provider
adapters, session/event integration, and scoped MCP capabilities. The product server owns new-user
registration and requests on-demand provisioning through this service boundary. The resulting
agents run in OpenAI-hosted environments, not one CapRover agent-core container per user.

The target assigns each user one logical team (one orchestrator and 2–3 specialists). The current
shop-shared configuration and offline foundation do not yet establish that target. Before resuming
integration, follow the [alignment checklist](../../docs/agent-integration.md); existing setup and
contracts below describe implementation evidence, not completed hosted provisioning.

## Development

Run all commands from `services/agent-core/` in the task worktree:

```bash
make install
make lint
.venv/bin/pytest tests/contracts tests/storage tests/runs tests/integration -v
make ci
make docker
.venv/bin/python -m scripts.verify_volume_restart
```

Use Python 3.14 (`python3` on PATH; CI installs it). Dependencies are pinned in requirements files.
Copy `.env.example` to ignored `.env`, fill the signing key locally, and pass it via
`.venv/bin/uvicorn app.main:app --env-file .env --port 8000 --workers 1 --no-access-log`.
`make run` retains the template development command; it expects exported configuration.
Never commit runtime `.env`, provider credentials, DB files, or generated evidence.
Tests block external socket connections and permit loopback; they need no OpenAI key.
One upstream Starlette warning currently reports its deprecation of httpx TestClient support;
the repo template's pinned httpx remains functional. T01 does not add a second HTTP client.

## Configuration

Every variable is listed in `.env.example`. Required values have no implicit deployment fallback.
Validation errors name the variable and omit its value. No real secrets are in sample config.

| Variable | Meaning/default |
| --- | --- |
| `APP_ENV` | Required: local, test, develop, production |
| `PORT` | 8000; container/service port |
| `AGENT_PROVIDER` | Required: fake or openai_agents; fake only in local/test |
| `AUTH_MODE` | Required: fixture or jwt; fixture only in local/test |
| `DATABASE_URL` | Required durable SQLite URL; local sqlite:///./data/agent-core.db; container sqlite:////data/agent-core.db |
| `CONFIG_PATH` | Required immutable registry path, e.g. config/registry.json |
| `DATA_MCP_MODE` | Required mock or remote; remote forbids mounting the mock Data server |
| `DATA_MCP_URL` | Required bootstrap endpoint; local http://127.0.0.1:8000/mcp/data; remote requires an approved internal URL |
| `KNOWLEDGE_MEMORY_MCP_URL` | Required bootstrap endpoint; local http://127.0.0.1:8000/mcp/knowledge-memory |
| `MCP_TOKEN_SIGNING_KEY` | Required secret, at least 32 bytes; runtime only |
| `OPENAI_API_KEY` | Required only for openai_agents; runtime secret |
| `OPENAI_MODEL` | Required only for openai_agents; no default model |
| `AUTH_JWKS_URL` | Required HTTPS JWKS endpoint in jwt mode |
| `AUTH_ISSUER`, `AUTH_AUDIENCE` | Required trusted issuer/audience in jwt mode |
| `RUN_TIMEOUT_SECONDS` | 180 from enqueue, including queue time |
| `RECOVERY_TIMEOUT_SECONDS` | 60 additional seconds after the run deadline |
| `MCP_TIMEOUT_SECONDS` | 15 per call, also bounded by remaining run time |
| `MAX_TOOL_CALLS_PER_RUN` | 8; configurable downward |
| `MAX_CONCURRENT_RUNS` | 4; configurable downward |
| `HISTORY_RETENTION_DAYS` | 30; operator prune command default |

Registry snapshots are authoritative for conversation model, capabilities, knowledge versions and
MCP URLs. Bootstrap URL env vars are supplied to T04's server/bridge factory; they do not overwrite
persisted revisions or conversations. To use a new endpoint/model, publish a NEW registry revision
containing the configured values, activate it administratively, and create a new conversation.
The sample registry's `fixture-only` model is offline configuration; a live revision must specify
the account's supported `OPENAI_MODEL`. The official `openai==3.42.0` runtime SDK is pinned and exercised by both mocked wire tests
and synthetic live acceptance. Agents SDK/Responses loops are not substituted.

## Composition and shared contracts

Initial foundation SHA: `9ce01a24f19acdfc4e5803faec1e1a3fa1fd678f`.
Shared contract amendment: `94ef8f9c4e25e0af4e321865378bdce718b5fdba` on local
`feat/agent-core-template`. New T02–T04 worktrees start from the amended SHA; existing
worktrees based on the initial foundation import the amendment before integration.
See [contracts/README.md](contracts/README.md) and `app/contracts/` for all signatures.

`create_app` accepts injected provider and bridge plus:

- `router_factory(repository, settings, readiness) -> APIRouter` wraps T02 auth/router factories.
- `mcp_factory(repository, settings) -> {mount_path: ASGIApp}` supplies T04 mounted servers.
- Prebuilt `api_router` / `mcp_apps` are alternatives for callers that already share dependencies.

All factories receive the same repository/settings. Child ASGI router lifespan contexts start before
the worker, and close after it stops. FastAPI/Starlette server factories must return their lifespan
aware app (including MCP session-manager startup). No worker/provider implementation imports API
routes or MCP internals. Factory wiring is tested using test-only boundary doubles; this does not
claim real MCP transport or live Agents API acceptance.

## Durability and operational rules

SQLite uses foreign keys, WAL, a 5-second busy timeout, short BEGIN IMMEDIATE transactions and schema
versioning. UUID resources and UTC timestamps are application-generated. A unique partial index
permits one nonterminal run per conversation. The user message/run/lock commit before returning.
Replay precedes busy checking; payload/key conflicts are explicit. Cursors identify an existing
message/event inside the authorized resource and paginate by monotonic sequence, never offset.

Subscribe before submitting follow-up input. Initial input is submitted atomically at creation;
its session mapping and accepted receipt persist together. Creation/input markers precede external
mutations. Inspect provider root state after stream loss; a subagent event or stream closure never
unlocks the conversation. Persist tool results before delivery, and replay only a call currently
pending at the provider. Tool/source deduplication uses session/turn/call and provider item IDs.
Sources in final responses must come from persisted successful tool results.

After timeout request cancellation and confirm root status. At the recovery deadline, unresolved
outcomes become failed/provider_outcome_unknown and the conversation stays blocked. Do not unlock or
resubmit automatically. Investigate the provider session, then delete the scoped conversation/session
or have the user create a separate conversation. Unknown session creation without a saved session ID
cannot currently be found by correlation; it requires provider-side administrative investigation.

`/health` is liveness; `/ready` checks configuration initialization, DB, adapter wiring and the worker
heartbeat (5 seconds). T02 also exposes the spec's `/api/v1/health` and `/api/v1/ready` through its router.
The worker records aggregate run status counts, queue delay, run/tool latency and provider/MCP error
counts in `app.state.worker.metrics`; log records contain JSON run ID/status/latency/sanitized code.
Enqueue captures trusted grants from AuthContext.scope for durable MCP credentials; ownership uses
only tenant/shop/user. No grants are inferred from model input. No prompts, responses, tool payloads,
identity or credentials are logged. Container access logs are
disabled. Metrics reset when the process restarts and are not an accounting ledger.

## Maintenance

Run trusted operator commands with the app STOPPED. They take the same exclusive database ownership
lock as the service. A second application worker, container, or maintenance command is rejected.
Keep one replica and one uvicorn worker; disable overlapping old/new containers using the same DB.
Never bypass the ownership lock to run two versions against the volume.

Add a new immutable registry entry, then activate for the shop:

```bash
.venv/bin/python -m scripts.activate_revision --tenant tenant-a --shop shop-a --user operator \
  --template shopops --revision returns-v2
```

Provisioning with a different revision still returns configuration_conflict; it is not an update API.
Existing conversations retain their snapshot; new conversations use the active revision.

Delete a terminal/blocked conversation and its provider session with the trusted T03 factory:

```bash
.venv/bin/python -m scripts.cleanup_conversation delete --tenant tenant-a --shop shop-a \
  --user user-a --conversation UUID --provider-factory YOUR_MODULE:YOUR_FACTORY
.venv/bin/python -m scripts.cleanup_conversation prune
```

The factory accepts Settings and returns AgentProvider. A missing factory never reports successful
provider deletion. A failed provider deletion leaves the row/history and cleanup_failed status visible;
retry after inspecting the provider. Active runs cannot be deleted. Pruning removes only terminal-run
messages/events older than HISTORY_RETENTION_DAYS (or `--before` ISO UTC), preserving run/key/session
mappings, user-message receipt metadata and monotonic sequence counters. Same-payload replays
retain their original IDs after pruning; deleted history is not restored. Schedule pruning through the operator's tooling.

## Offline demo and remaining integration

After T02–T04 handoffs, compose the factories above and run:

```bash
.venv/bin/python -m scripts.demo_offline --fixture-token FIXTURE_TOKEN --shop shop-a
```

This loopback-only client provisions, creates a conversation, submits synthetic questions and polls
results. The default fake provider asks for clarification; configured fake scenarios in integration
tests exercise deterministic data/knowledge/history calls over real loopback MCP. For real model
selection of tools, use the explicit live smoke below. AC13 has passed with synthetic fixture data;
this does not establish real shop or production deployment acceptance.

## Container / CapRover

The image runs UID 1001, copies config/knowledge/fixtures/contracts/scripts, and owns writable `/data`.
Mount a persistent volume at `/data` and set DATABASE_URL=sqlite:////data/agent-core.db. Existing volumes
must be writable by UID 1001. Deploy one instance with no overlap. Internal-only service: enable
"Do not expose as web app", no public domain/Port Mapping; clients call
http://srv-captain--agent-core-dev:8000 (dev) or http://srv-captain--agent-core:8000 (production).
Keep internal MCP routes off public ingress. Other service endpoints use runtime *_URL variables and
cluster addresses, never another service's public domain or a default dev URL.

`service.json` declares stack python / port 8000; the shared pipeline runs make ci and discovers this
service without workflow changes. Dev setup requires CapRover app agent-core-dev,
AGENT_CORE_DEV_APP_NAME / AGENT_CORE_DEV_CAPROVER_TOKEN, and shared CAPROVER_SERVER. Production needs
app agent-core and matching PROD secrets before merge to main. These are deployment prerequisites;
T01 does not create them, push branches, or invoke /deploy. Completed integration targets develop.

## Integrated offline workflow

All four module branches are included on `feat/agent-core-template`. Default startup constructs the
API/auth adapter, SQLite repository, local/test fake provider, MCP bridge and MCP subapps using the
same repository and configured signing key. The bridge uses real HTTP and signed scoped tokens.
`httpx==0.28.1` is a runtime dependency; no MCP transport package or duplicate HTTP client was added.

Both `/mcp/data` and `/mcp/data/` (and their knowledge equivalents) reach the same MCP root without
redirects. Existing immutable slashless revision URLs remain unchanged. MCP routes require their
own scoped credentials; application bearer tokens do not grant MCP access. Keep these routes on
an internal service/ingress as described above.

Registry snapshots, not environment overrides, supply conversation-pinned MCP URLs. For an approved
real MCP profile, add its name to the top-level `approved_remote_profiles` array in CONFIG_PATH after
confirming the scoped-auth/schema contract. Unapproved profiles fail startup and administrative
activation. The bridge allowlist includes every registered revision URL; this preserves old/new
snapshots. Remote mode disables the mock Data mount; drain old mock conversations before disabling
it. HTTP loopback endpoints are allowed only for local/test deployment.

Verification: `tests/integration/test_mcp_workflow.py` runs a real HTTP service with SQLite, fixture
authentication, T03's explicitly configured fake scenarios and both MCP servers. It checks 5% baseline
versus 15% current returns (+10 percentage points), knowledge references, current-conversation history,
follow-ups, cross-owner denial, readiness and remote-profile preflight. The fake scenarios are fixed
synthetic test inputs, not evidence of live model reasoning. The default fake provider asks for
clarification unless scenarios are supplied explicitly; its in-memory provider sessions do not
survive a process restart, while SQLite history and receipts remain durable.

## Live OpenAI validation

`AGENT_PROVIDER=openai_agents` selects the official SDK adapter. It creates a session with
`environment.type=none` and the first input together, persists the session and accepted-input
receipt atomically, and reconciles the saved root turn without resending that first message.
Initial run correlation uses session metadata; follow-up submission keys and persisted root IDs
support recovery. Unknown creation outcomes still block rather than creating replacement sessions.
Only successful persisted tool results from that session/turn can authorize response citations.
The application closes its SDK client during shutdown. Definite request rejection is reported as
`provider_request_rejected` without leaking the upstream error body.

For a local synthetic live smoke, supply `OPENAI_API_KEY` and `OPENAI_MODEL` in the process environment
or explicitly select an ignored credentials file. The runner reads only those two settings from
that file; it does not copy the file or implicitly search the original checkout's root `.env`.
Run from this service directory:

```bash
.venv/bin/python -m scripts.demo_live --live --credentials-file .env --evidence .evidence/live-smoke.json
```

`--model` can explicitly override the model setting. The smoke creates a temporary SQLite database
and HTTP server with fixture identity and real scoped MCP transport, makes three synthetic turns
(metrics, same-session follow-up, knowledge), then stops the worker and cleans up every known remote
session independently of local deletion. If remote deletion cannot be confirmed, it preserves
recovery state and reports its location. The three-turn count and run/request timeouts bound this
smoke; no monetary cap is promised. The tested API deployment rejected the optional `spend_control`
field, so this integration does not send it.

For the opt-in pytest gate, export the key/model into the environment first:

```bash
AGENT_CORE_LIVE=1 .venv/bin/pytest -v tests/live/test_agents_api.py
```

Live-marked tests may access OpenAI only with that explicit opt-in. Other tests retain the offline
network guard even when the flag is set. Default `make ci` skips live acceptance and performs no
real API calls. The official SDK compatibility test uses MockTransport and now runs in default CI.

AC13 was verified with `gpt-6-astra`: three completed turns, 5%/15% metrics and 10-point change,
source-grounded knowledge, follow-up in one session, and confirmed remote/local cleanup. This is
synthetic local integration evidence; real shop data, external Data MCP/JWT deployment settings,
and CapRover deployment still require their own configuration and checks.

## Hosted runtime foundation (T05)

Runtime profiles are immutable registry revision data. Legacy snapshots normalize to
`conversation-v1` / `none` independently of the active revision. `RUNTIME_BUNDLE_PATH` defaults to
`runtime-bundles`; it is an operator-controlled service-local directory, never a request parameter.
`config/registry-hosted.example.json` preserves `returns-hosted-v1` / bundle `1.0.0` and appends
`returns-hosted-v2` / bundle `1.1.0` for product investigation policy. Each has a verified SHA-256;
the old bundle directory and revision remain immutable. Activate the new revision explicitly for
new conversations; existing snapshots keep their pins. Its `gpt-6-astra` model is an explicit
example, not a default: set OPENAI_MODEL explicitly
and publish a new matching registry revision before using another model. The example's loopback
MCP URLs are local/test only; dev deployments need approved cluster endpoints throughout the
registry. The legacy default registry remains unchanged. The image includes runtime-bundles/.
RUNTIME_BUNDLE_PATH must name an existing relative directory inside this service; absolute paths,
parent traversal and symlink escapes fail before provider I/O. Both startup validation and live
session creation use the selected directory.

Message submission accepts `output_mode=text|report` (default text). Report is invalid for legacy
profiles and participates in replay/conflict checks. Hosted report answers need a validated root
report; clarification/cannot_answer can finish without a report. Artifacts are listed at
`GET /api/v1/runs/{run_id}/artifacts` and downloaded as attachments at
`GET /api/v1/artifacts/{artifact_id}/content`, using `history:read` and the existing identity scope.
Provider IDs, bundle payloads and paths are never public inputs.

Schema migration 002 preserves existing rows, adds runtime ownership and artifact metadata, and
keeps one SQLite owner. Unknown remote outcomes retain blocking/recovery mappings. Provider
cleanup and bundle packaging are integrated; final T08 hosted evidence remains separately tracked.
No hosted result is inferred from offline tests. See `contracts/managed-runtime.md`.

The durable setup budget is 60 seconds within the run deadline. First observed connection after
that budget fails even if the provider now reports connected; established sessions do not receive
a second setup deadline. Known session/environment IDs are retained for cleanup and recovery.

## Product investigation policy

The opt-in `returns-hosted-v2` bundles a `product-investigation` skill and freshness/six-workflow
references alongside the existing returns helper and data/knowledge specialists. It starts with
granted summaries, follows permitted source evidence, checks dates/observed_at/revisions/coverage,
and treats a future granted pull-latest as pending until status reconciliation and an evidence
reread verify freshness. Data refresh never grants merchant writes. The frozen report-v1 stays
returns metrics plus versioned policy findings; broader workflows remain capability-aware guidance.

Today's four read-only fixture tools expose no raw-record fetch, catalog, refresh request/status or
revision/coverage guarantees. Neither this policy nor an approved remote-profile name adds those
tools. Approved runtime-registered MCP connections may use runtime-managed authentication; the agent
never reads a vault/token, selects alternate transport or derives grants from user text. See the
[integration seam and limits](contracts/product-investigation.md). Offline policy/packaging checks
do not establish live MCP, hosted team, refresh, or merchant-operation acceptance. Existing hosted
smoke tooling remains pinned to the old `1.0.0` fixture workflow and does not accept the new workflow.


## Hosted acceptance (T08)

The hosted CLI is separate from the original `none` smoke and requires both acknowledgements:

```bash
OPENAI_MODEL=<supported-model> .venv/bin/python -m scripts.demo_live_hosted --live --hosted \
  --credentials-file <existing-ignored-file> --evidence .evidence/live-hosted.json
```

The explicit loader reads only key/model; it never copies credentials into the worktree or sandbox.
This is billable model/container work using synthetic fixtures, at most two small sandboxes and three
application turns. The runner verifies actual saved commands, approved skill/helper bytes, two child
identities, scoped report metrics, follow-up and isolation. It always attempts remote cleanup; unknown
outcomes preserve recovery state. Default CI skips both live tests; enabling legacy live alone cannot
enable hosted execution. A live failure includes only its fixed stage and safe run status/error.
See [hosted acceptance and recovery](contracts/hosted-acceptance.md) and the tracker for current
verification. A connected sandbox alone does not satisfy end-to-end hosted acceptance.


Current integrated checks: 428 offline tests passed; both live suites skipped by default; Docker
build and recorded volume recreation passed. Four authorized hosted attempts were cleaned up.
The final attempt verified the approved helper and skill reads, but exact boundary-probe proof and
child role binding remain unverified (`instructions=null`). Full hosted acceptance is NOT ACCEPTED;
artifact/follow-up/isolation live checks did not run past that proof gate. See the tracker before
merging or treating this template as accepted for a real integration.


## T09 chat adapter fixture

The single demo phone in `shopops-chat-api` uses the existing `local-alice` credential,
restricted by that adapter to `shop-a`. Existing Core fixtures and permissions are unchanged.
The first successful login ensures only the configured logical orchestrator. Core creates its
provider session/environment on first input. Operator activation of an immutable hosted revision
is still required; hosted proof gates from T08 remain UNVERIFIED.

`tests/chat_loopback.py` is a test-only process fixture using the actual Core app, worker and its
own SQLite database with an explicit synthetic provider/tools. It refuses external network
connections and is not shipped as a production app. Install Core's private Python3.14 test
environment, then run the chat API's `AGENT_CORE_LOOPBACK=1` offline acceptance separately from
independent service CI. Report/download and restart results from this fixture prove the HTTP
application boundary, not real skill, specialist or sandbox execution.

## Commerce data profile (T10)

Use `config/registry.shop-data.example.json` and the operator-owned
`config/shop-data-bindings.example.json` for the opt-in `shop-data-read-v1` profile.
The new revision is `returns-hosted-data-v1`; the old revisions remain available for
pinned conversations. The approved runtime bundle bytes/digest are unchanged.

Set `CONFIG_PATH` to that registry, `DATA_MCP_MODE=remote`,
`SHOP_DATA_BINDINGS_PATH` to the mounted trusted binding file and
`SHOP_DATA_MCP_URL=http://localhost:8003/mcp` locally. Set the registry revision's
`data_mcp_url` to the **same** endpoint. For CapRover use
`http://srv-captain--shop-data-mcp-dev:8000/mcp` (dev) or
`http://srv-captain--shop-data-mcp:8000/mcp` (production). Keep Data MCP and its
source/processor private. Existing `DATA_MCP_URL`/`KNOWLEDGE_MEMORY_MCP_URL` settings
remain required by the legacy service configuration. The environment verifies an
approved registry endpoint; it does not rewrite any pinned conversation URL.
Retain prior approved endpoint revisions and binding versions until their
conversations are retired.

The synthetic binding retains Core `tenant-a` / `alice` / `shop-a` and maps to
source phone `+84900000001`, shop `shopee-open-platform:1001`. This is a one-phone
demo, not production phone authentication. The versioned binding digest covers
all fields, including `coverage_start`; never obtain bindings from browser/model
arguments. Update the binding and its digest via a new administrative revision
and create a new conversation after reconciling pending work. Do not silently
retarget old conversations. Generate the reference with `Binding.reference` from
`app.tools.shop_bindings` after validating the operator-owned binding JSON.

Before activation, seed the source and successfully synchronize the processor,
apply the Data MCP source membership and derived projection migrations, provision
restricted query/membership roles, and mount MCP catalog/config/CA. See the Data MCP
[setup](../shop-data-mcp/INTEGRATION.md). DSNs, CA files and database credentials stay
with Data MCP. The four datasets in `catalog.agent.example.json` require only
`data:read`. Core never exposes SQL, refresh, CRUD or raw approval tools to the model.

The example's `coverage_start=2026-10-17` is for the verified synthetic seed; it is
not a promise about arbitrary upstream history. Both requested and preceding
baseline intervals must fit the declared complete-history range and the frozen
pipeline `analysis_as_of`. Missing publication, unknown SKU, incomplete or truncated
results and changed revisions fail closed. `queried_at` and refresh time are not
proof of coverage or live data freshness. See the [metric contract](contracts/shop-data-integration.md)
for order-cohort return-request semantics and safe review samples.

Offline acceptance uses `scripts/t10_acceptance.py` with real disposable PostgreSQL
and HTTP services, and a test-only fake model provider. It requires Docker and each
service's own installed dependencies; use `--help` for invocation. It never targets
an operational database. Hosted acceptance is separate: T08/T09 evidence and
explicit operator opt-in are required before paid calls. Offline success does not
prove hosted child roles or sandbox boundaries.


## CapRover T10 demo preset

The committed [Core settings](config/caprover-agent-core.env.example),
[chat API settings](config/caprover-chat-api.env.example) and
[develop registry](config/registry.shop-data.develop.example.json) are one matching
preset for the standard `*-dev` app names. Merge settings into each app's runtime
configuration; keep existing secrets and durable database paths. The Core image must
contain this preset before setting its `CONFIG_PATH` to the new file. Runtime app
settings are not populated by merging a PR or deploying an image.

The develop registry adds `returns-hosted-data-dev-v1` for the internal Data MCP URL.
It retains every existing hosted/data revision and binding, including hosted v2;
old conversations keep their snapshots. The new data revision reuses T10's approved
bundle without changing its bytes. Setting `SHOP_DATA_MCP_URL` alone cannot replace
the localhost URL pinned by the local example. A different endpoint needs another
immutable revision and a matching chat API setting.

Apply in this order:

1. Complete the Data MCP [database/config setup](../shop-data-mcp/INTEGRATION.md),
   including source membership, the four agent projections, restricted roles,
   `catalog.agent.example.json`, configured dataset access, verified PostgreSQL CA,
   seeded source data and a successfully published processor snapshot. Set its
   `MCP_INTERNAL_URL=http://srv-captain--shop-data-mcp-dev:8000/mcp`.
2. Deploy the Core image containing this registry. Apply the Core settings with
   `OPENAI_API_KEY` and a stable `MCP_TOKEN_SIGNING_KEY` supplied separately. This
   preset uses `APP_ENV=local`/`AUTH_MODE=fixture` for the single synthetic owner;
   this selects demo authentication and does not change the OpenAI-hosted profile.
   Keep one worker/replica, writable persistent `/data` owned by UID1001 and no
   overlapping database owners. Wait for `Application startup complete`.
3. If the shop already has an orchestrator at another revision, first reconcile
   unresolved work under the previous settings. Follow the stopped-app
   [maintenance workflow](#maintenance) to activate `returns-hosted-data-dev-v1`.
   Do not edit stored snapshots, erase history or discard an uncertain submission.
   A new shop's first login provisions this revision without a separate activation.
4. Apply the chat API settings. Keep its own existing writable database volume;
   never mount Core's database there. Leave the OpenAI key in Core. Wait for startup.
5. Confirm the frontend HTTPS `/api/chat/auth/config` returns
   `{"mode":"demo_phone"}`, reload the UI, and sign in with `+84900000001`.
   Login provisions/reuses the logical orchestrator; it does not create an OpenAI
   session or submit model input. The previous T09 number is no longer supported.
6. Send a first message only when ready for a live hosted call. Follow-up and report
   checks remain separate from successful login. T08 hosted proof gates and actual
   pipeline freshness are not established by deployment or offline configuration tests.

The frontend runtime upstream remains
`SHOPOPS_CHAT_API_URL=http://srv-captain--shopops-chat-api-dev:8000`, with container
port80 and valid HTTPS for its public domain. Backend containers use port8000 and
private cluster URLs. Do not change either service's database path just to apply the
preset, and do not put provider credentials in browser configuration.


The Luna preset selects `OPENAI_MODEL=gpt-6-luna` and chat revision
`returns-hosted-data-luna-dev-v1`. This adds a separate immutable revision; the
Astra revisions remain unchanged. Reconcile pending work and activate this revision
using the stopped-app maintenance workflow before changing the chat namespace.
New conversations select Luna; existing conversations keep their original model.
Account access and Agents API compatibility require a separate live check.
