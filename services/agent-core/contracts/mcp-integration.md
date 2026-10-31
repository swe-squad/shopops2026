# MCP tools v1 — T04 integration handoff

## Factories and ownership

- `app.tools.credentials.Credentials(signing_key)` implements the foundation credential contract.
  T01 supplies `MCP_TOKEN_SIGNING_KEY` from runtime configuration, at least 32 UTF-8 bytes.
- `app.mcp.data.build_data_app(repository=..., credentials=..., mode="mock")` returns a
  FastAPI ASGI app. `mode="remote"` returns `None` without loading fixtures. T01 omits
  the Data mount in remote deployments. Existing pinned mock conversations need their
  mock endpoint to remain available during migration; drain them before disabling it.
- `app.mcp.knowledge_memory.build_knowledge_memory_app(repository=..., credentials=...)`
  loads and checks the immutable default bundle at startup. `bundle_path` selects a
  trusted administrative bundle directory; it never comes from model input. Keep an
  app/endpoint for each version still pinned by a conversation. Unknown versions return
  `not_found`, never silently use the newest bundle.
- `app.tools.client.MCPClient(allowed_urls=frozenset(...), allow_loopback=False)` accepts
  exact URLs from the administrative revision registry, including all still-active old
  revisions. Set `allow_loopback=True` explicitly for local/test deployments only.
- `app.tools.bridge.MCPToolBridge` (or `build_bridge`) takes the same `repository`,
  `credentials`, and `client`. An optional trusted async
  `permission_resolver(scope, conversation_id)` can further restrict the run grants.
  `definitions(config)` and `execute(scope, conversation_id, config, call)` implement
  the frozen `ToolBridge` protocol. Call `validate_profile(snapshot)` at startup for
  every deployed revision; missing URL or unapproved remote auth must prevent activation.

T01 owns application mounting, config/env loading, repository persistence and the worker.
This module does not construct a database, worker or provider. The bridge validates the
stored conversation and exact config snapshot before credential issuance; the MCP servers
independently validate the conversation owner and revision before any business/history read.

Import T01's shared-contract amendment `94ef8f9` (cherry-picked on this branch as `a244c9c`)
before integration. The worker supplies the persisted `Run.scope` with verified enqueue-time
permissions; an identity-only Scope has no tool grants. Data and knowledge tools require
`conversation:write`; history requires `history:read`, independently of conversation access.
These are the standard T02 permissions; no extra permission names or implicit grants exist.
The optional resolver only intersects these trusted run grants and cannot add privileges.
The issuer rejects permission escalation. Tokens restore the same grants into verified Scope.
Ownership comparisons use tenant/shop/user, so changed grants do not create another identity.

## Shared changes requested from T01

1. Move the existing `httpx==0.28.1` pin from dev-only to runtime requirements. No new
   package is needed: v1 uses FastAPI, Pydantic, httpx and Python's HMAC primitives.
2. Mount the ASGI factories using the shared repository/settings, skipping a `None` Data
   app. Include `fixtures/business/` and `knowledge/` in the runtime image.
3. For `app.mount("/mcp/data", data_app)` and `app.mount("/mcp/knowledge-memory", memory_app)`,
   the canonical URLs are `/mcp/data/` and `/mcp/knowledge-memory/`. Foundation registry
   examples omit the final slash: publish a coordinated configuration revision using the
   canonical URLs, or provide exact-path ASGI dispatch in T01. The bridge never follows
   the framework's 307 redirect. Do not rewrite an already-persisted immutable revision.
4. Document/load the existing variables `DATA_MCP_MODE`, `DATA_MCP_URL`,
   `KNOWLEDGE_MEMORY_MCP_URL`, `MCP_TOKEN_SIGNING_KEY`, `MCP_TIMEOUT_SECONDS` in `.env.example`
   and README; no additional runtime environment variable is introduced by T04.
5. Pass the trusted persisted run Scope and approve remote profiles only after the remote service
   implements the same credential/schema contract. No fallback to unauthenticated calls.

## MCP protocol

The client/server implement MCP `2025-06-18` Streamable HTTP with JSON-RPC 2.0:
initialize, initialized notification, ping, tools/list and tools/call. The server is
stateless and returns JSON, not an SSE GET stream; authenticated GET returns 405.
The client supports both JSON and SSE POST responses, optional per-call MCP session IDs
and DELETE cleanup on success or failure. Cleanup skips the response body and is best effort,
with at most one second inside the remaining call budget. Cancellation or budget exhaustion
propagates immediately; remote servers must expire abandoned sessions too. No session is
reused between conversations/users. Server requests
for sampling/elicitation are unsupported and never advertised. Initialization and all
subsequent HTTP messages carry the scoped bearer token; subsequent messages also carry
`MCP-Protocol-Version`. POST Accept includes JSON and event-stream.

The server rejects browser Origins unless explicitly approved via `allowed_origins`.
It authenticates before parsing the body, bounds requests to 64 KiB, and independently
checks the conversation for initialization/list/call. Tool results include MCP text
content and `structuredContent` containing the identical ToolResult envelope.

Reference: [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports),
[lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle),
[tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).

## Scoped credentials

HS256 only; issuer `agent-core`; audiences `agent-core:data` and
`agent-core:knowledge-memory`; 60-second lifetime; zero expiry leeway. Required claims:
`iss`, `aud`, `iat`, `exp`, `jti`, `tenant_id`, `shop_id`, `user_id`, `conversation_id`,
`permissions`, `config_revision`. `iat`/`exp` are integer Unix timestamps. Missing/blank
identity, future issuance, invalid signature, unexpected algorithm, wrong audience,
expired token, lifetime over 60 seconds and mismatched full scope are rejected.

Credential verification happens before repository access. A valid signed credential for
another owner/conversation/revision is denied before business data/history reads. Tokens
never come from model input and are never logged. All responses use sanitized error codes.
This is service-to-service authentication, not the public application's bearer tokens or
a general OAuth authorization server. A remote endpoint must explicitly support it.

## Function and result contracts

`tools/v1/<name>.json` publishes the function argument schemas; `<name>.data.json` publishes
typed success data and `tool-result.json` the shared envelope. All objects reject undeclared
properties. No tool takes identity, SQL, paths, endpoints, credentials, bundle versions or
an arbitrary tool name. The bridge maps the four published names to the same fixed MCP
names and never discovers/grants tools from an upstream tools/list response.

- `get_return_metrics(sku, start_date, end_date)` and `get_review_summary(...)` use inclusive
  ISO calendar dates in Asia/Ho_Chi_Minh. Require 1..90 inclusive days and SKU length 1..64.
  Baseline is the immediately preceding interval of the same inclusive length. Reject dates
  that cannot represent that preceding interval (for example 0001-01-01). Rates are
  percentages rounded to six decimals; zero orders has `return_rate: null`, not zero.
  Metrics contain sku, dates, timezone, orders, returns, return_rate, baseline counts/dates,
  and change_percentage_points. Reviews contain sku, dates and categories with count and
  synthetic evidence references.
- `search_knowledge(query, limit=5)` requires 1..1000 characters and nonblank text; limit
  is an integer 1..20. Results contain matches with document_id, chunk_id, excerpt,
  bundle_id and version. Deterministic case-insensitive lexical token overlap ranks hits;
  ties use document/chunk ID. No match returns an empty array.
- `get_conversation_history(before_sequence=null, limit=20)` requires a positive integer
  sequence when present. It returns up to limit messages strictly before that sequence,
  in increasing sequence order. No boundary means the latest messages. The foundation
  repository exposes forward opaque cursors; the adapter pages authorized history at
  100 items per request and keeps at most 20 messages in memory. This costs O(history)
  reads; T01 can later optimize the repository while preserving semantics.

Success envelope: `schema_version: "1"`, `data`, `sources`, `observed_at` (timezone-aware ISO
instant), `error: null`. Error envelope has `data: null`, `sources: []`, `observed_at: null`
and one of `invalid_input`, `not_found`, `permission_denied`, `upstream_unavailable`, `timeout`.
The bridge validates typed output, query fields, exact preceding baseline interval, bundle identity, history conversation,
ordering/boundary/limit and knowledge/history source references before returning success.

Serialized UTF-8 ToolResult maximum is 32 KiB. Oversized or malformed output fails with
`upstream_unavailable`; it is never silently truncated. MCP wire framing is independently
bounded at 256 KiB (includes duplicated text/structured content). Known SKU outside the
fixture dates returns empty counts/null rate; unknown tenant/shop/SKU returns `not_found`.
Connection failures do not become empty datasets. HTTP auth denial is permission_denied.

The bridge applies a total 15-second budget across authorization, initialization, tools,
cleanup and retry backoff. Individual client calls also have a 15-second cap. At most two
retries follow transient read-only HTTP 429/500/502/503/504, transport failures or timeout.
Permission, input, not-found and malformed protocol/output are not retried. A smaller test
budget is injectable. No provider mutation is performed here. Worker run limits and result
persistence/deduplication remain T01's responsibility.

Endpoint policy: exact administrative allowlist; HTTP(S) only; no userinfo, query or fragment;
redirects refused; environment proxy settings disabled. Metadata hostnames, link-local,
unspecified and multicast addresses are blocked, including IPv4-mapped IPv6 and AWS IPv6
metadata. All DNS answers are checked and the connection uses a checked numeric address
with the original HTTP Host and TLS SNI, preventing a second DNS lookup from rebinding it.

## Fixtures and verification

The synthetic data references T02 identities: tenant-a/shop-a with alice and bob;
tenant-a/shop-b with alice. This is metadata for demos, not a second auth database.
SKU-A baseline is 2026-10-12..18 (100 orders, 5 returns); current is 2026-10-19..25
(100 orders, 15 returns). Shop-b is distinct (1% current returns). Sizing complaints
have synthetic review references. Knowledge manifests bind document SHA-256 hashes plus
a SHA-256 of the canonical document list; startup rejects tampering and path escape.

From this service: `.venv/bin/pytest tests/tools tests/mcp -v` and `make lint`.
Tests allocate ephemeral loopback ports; no external network or OpenAI credentials.
The transport tests cover both mounted servers and an independent SSE/session peer.
A module-level profile test retains an old endpoint and uses an approved remote profile
for a new conversation. Real activation persistence, production mounting and history
ownership with SQLite remain T01/T02 integration evidence; live provider tool delivery
remains T03 integration evidence. None of these missing gates is marked passed here.

## Integrated application wiring

The integration branch now promotes httpx to runtime, builds the bridge and both MCP subapps
from the shared repository/settings, and supports exact slashless URLs without redirecting
or mutating old snapshots. `app.composition.build_configured_bridge` validates the deployed
registry before readiness and before the administrative activation command. The optional
top-level registry array `approved_remote_profiles` records compatibility approvals; it is
operator configuration, never a request/model argument.

The complete local HTTP/SQLite workflow, including knowledge/history and fixture identities,
is covered by `tests/integration/test_mcp_workflow.py`. This extends the module-level evidence
above. Live OpenAI delivery and external remote-peer TLS/SNI acceptance remain unverified.
