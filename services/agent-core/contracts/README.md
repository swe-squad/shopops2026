# Shared foundation contract v1

Python contracts in `app/contracts/` are the source of truth. All I/O interfaces are async;
SQLite uses `asyncio.to_thread` and a separate connection per short transaction.
Models are Pydantic frozen records with forbidden extra fields. JSON uses UTF-8, UUID
strings, ISO-8601 UTC timestamps, string enum values and arrays for tuples/frozensets.
`Scope` always contains tenant, shop and user; AuthContext is trusted adapter output.
Repositories enforce tenant/shop/owner on conversations, runs, messages and events.
Orchestrators are shop-shared configuration. No provider network work occurs at import.

## Consumer factories

T02 exports `build_api_router(repository: Repository, authenticate: Callable[[str],
Awaitable[AuthContext]], readiness: Callable[[], Awaitable[bool]]) -> APIRouter`.
The router owns `/api/v1` including health/ready and translates typed CoreErrors to the
spec's envelope. Pass it to `create_app(api_router=..., provider=..., bridge=...)`.
T03 supplies AgentProvider; T04 supplies ToolBridge plus already-configured ASGI apps
passed as `mcp_apps={"/mcp/data": data_app, "/mcp/knowledge-memory": memory_app}`.
Factories must receive the SAME repository/settings instance through `router_factory`
and `mcp_factory` hooks documented in app/main.py; no second worker/database instance.
Missing adapters keep readiness false; the foundation never synthesizes a successful
business response or initializes an unverified live SDK.

## Persistence and idempotency

See complete signatures in `app/contracts/repository.py`. IdempotentResult.created is
true only on first commit; EnqueueResult contains stable persisted user Message and Run.
Message content is trimmed before hashing. Replay lookup precedes the busy check.
Conversation keys are scoped by tenant/shop/user; changed orchestrator or message payload
conflicts. UUID cursors resolve only inside the authorized resource, then paginate by
monotonic sequence (1..100 items, default 50). Message IDs are history cursors; event IDs
are event cursors; they are opaque, validated, and never interpreted as SQL/offsets.
User messages become durable at enqueue; assistant history contains only validated,
completed responses. Raw provider events/chain of thought are never persisted as events.

## Immutable revisions and activation

Registry entries define model, bundle/version, MCP profile/endpoints and allowlisted
capabilities. Deployed revision IDs are immutable: replacing their contents is rejected
when already persisted. `provision` never changes an existing revision and returns
configuration_conflict for a different revision. Administrative procedure: add a NEW
revision ID to CONFIG_PATH, deploy while keeping one DB owner, then run
`scripts/activate_revision.py --tenant ... --shop ... --user ... --template shopops
--revision <new>` in that deployment. This is a trusted operator command, not an HTTP
endpoint. It atomically advances the orchestrator; new conversations pin the new snapshot,
existing conversations/runs retain their old snapshot including endpoint URLs.

## Provider and recovery

`stream_events` returns an async context manager; enter and await `wait_ready` BEFORE
submit_input. Submission carries run UUID as correlation metadata. Snapshots expose
root identity and input_run_id. Subagent events never finish a root run. Inspect state
before submission and after stream closure. Persist session ID immediately. Mark
session_creating/submitting BEFORE mutations; no provider mutation is automatically retried.
Tool delivery is the exception: replay the SAME turn/call/result only when current provider
required_actions explicitly lists it (T03 must uphold provider call-ID idempotency).
The bridge is read-only in v1; unresolved tool execution after a crash can safely repeat,
but persisted tool results are reused. Unknown session creation cannot be recreated.
Session creation correlation lookup is a T03 extension; absent it, block at deadline.
Run deadline defaults to 180s from enqueue; recovery deadline is run deadline + 60s
(RECOVERY_TIMEOUT_SECONDS). Timeout requests cancellation, then inspects root state.
Only confirmed completion/failure/cancellation unlocks. Unknown outcomes after recovery
deadline become failed/provider_outcome_unknown with the conversation BLOCKED. No input
resubmission or automatic unblock. Operators delete the scoped conversation/provider
session after investigating; users can create another conversation.
Tool uniqueness is (session, root-turn, call ID), arguments/name must match on replay.
Persist before delivery; never count replayed calls against the eight-call limit twice.
RunEvent exposes status, tool name and sanitized code only. Source references must be a
subset of persisted successful tool results before an assistant response commits.

## Scoped MCP credential contract (T04 implementation)

Use HS256 only, issuer `agent-core`, audience `agent-core:data` or
`agent-core:knowledge-memory`, TTL 60 seconds, zero expiry leeway. Require `iss`, `aud`,
`iat`, `exp`, `jti`, `tenant_id`, `shop_id`, `user_id`, `conversation_id`, `permissions`,
`config_revision`. Derive all identity claims from stored Scope and trusted permissions;
never from model arguments. Signing key comes only from MCP_TOKEN_SIGNING_KEY. Validate
signature/algorithm, issuer, audience, time and full scope before accessing any data.
This contract is not a credential implementation; T04 owns issuance and verification.
