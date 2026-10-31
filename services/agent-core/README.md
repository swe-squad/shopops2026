# agent-core

FastAPI/Python 3.14 foundation for a durable, scoped ShopOps agent service on port 8000.
T01 supplies contracts, configuration, SQLite storage, scheduling/recovery, lifecycle and packaging.
T02 supplies auth/API routes, T03 supplies fake/live Agents API adapters, and T04 supplies MCP/tools.
Those three handoffs are required for the complete offline conversation demo. The standalone
foundation starts only with valid configuration and returns `/ready` 503 until adapters are wired.

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
| `AUTH_JWKS_URL` | Required HTTP(S) JWKS endpoint in jwt mode |
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
the account's supported `OPENAI_MODEL`. SDK verification/pinning is owned by T03; no unverified
Agents SDK or Responses loop is included as a substitute.

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

Subscribe before submitting input. Session creation/input submission markers persist before external
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

This loopback-only client provisions, creates a conversation, submits a synthetic returns question,
polls it and asks a policy follow-up. It needs T02's fixture token and T04's absolute-date fixture
compatibility. The script is supplied but the full scenario remains UNVERIFIED until those handoffs.
A test-only provider double cannot replace actual loopback MCP evidence. Live AC13 is separately
UNVERIFIED and belongs to T03; no credentials were read or copied for this task.

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

## T01–T03 integration status

The default app factory now mounts the application API with the configured fixture/JWT authenticator and the same SQLite repository used by the worker. In local/test mode, `AGENT_PROVIDER=fake` selects the delivered T03 fake provider. Other factories/providers can still be injected explicitly.

T04 MCP applications and a tool bridge are still required to start a complete worker workflow. Without them, `/ready` and `/api/v1/ready` return 503. Tests exercise the T01–T03 workflow with an explicitly named test-only bridge; they do not prove MCP acceptance. The live Agents API session-creation contract remains blocked, and no live-to-fake fallback is used. Runtime configuration is read from environment variables; the app does not implicitly load the original checkout's root `.env`.

Run the combined checks from this service directory with `.venv/bin/pytest` and `make lint`. The new `tests/integration/test_task_integration.py` checks persisted messages, follow-ups, trusted permissions, replay/conflict behavior and isolation against real SQLite.
