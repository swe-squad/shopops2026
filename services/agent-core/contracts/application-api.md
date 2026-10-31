# Application API v1 (T02)

`build_api_router(repository, authenticate, readiness)` returns an APIRouter with
`/api/v1` prefix. All three injected dependencies are async; authentication is a
callable taking a bearer token and returning shared `AuthContext`. Pass
`FixtureAuthenticator(...).authenticate` or `JWTAuthenticator(...).authenticate`.
Mount the router on the one T01 application; do not create a second repository or
worker. The foundation app factory has no injection hooks yet: T01 must add wiring.

## Authentication

Fixture adapter construction accepts only `app_env="local"|"test"`; T01 must pass
its validated APP_ENV explicitly and reject fixture mode outside those environments.
Synthetic tokens in `fixtures/identities.json`: `local-alice` (two shops),
`local-bob` (same shop, different owner), `local-carol` (another tenant).
These are public local test values, never production credentials.

JWT adapter requires a trusted HTTPS JWKS URL, issuer and audience. RS256 is the
only accepted algorithm. Keys are fetched/cached by PyJWT with a five-second
network timeout; verification and key fetching run off the event loop. Tokens
cannot select the JWKS URL. Require `kid` and claims `iss`, `aud`, `exp`,
`tenant_id`, `sub`, `shop_ids`, `permissions`. Tenant and subject must be nonempty
strings up to 128 characters; memberships/permissions must be arrays of nonempty
strings, never scalar strings or coerced numeric values. Expiry has zero leeway.
Invalid credentials return sanitized 401 with `WWW-Authenticate: Bearer`.

Scope is always tenant/shop/user. Shop routes check membership; resource routes
resolve through the repository for each authorized shop because foundation lookup
methods require full Scope. T01 repositories must enforce ownership and return
NotFound for foreign resources. Only NotFound permits trying another shop.
Within scope, required permissions are `orchestrator:provision`,
`conversation:write`, and `history:read` (including run/event reads).

## HTTP contract

See `application-api.openapi.json` for exported models and paths.

| Route (prefix /api/v1) | Success | Permission |
| --- | --- | --- |
| POST /shops/{shop_id}/orchestrator | 201 create, 200 replay | orchestrator:provision |
| POST /shops/{shop_id}/conversations | 201 create, 200 replay | conversation:write |
| POST /conversations/{id}/messages | 202, including replay | conversation:write |
| GET /runs/{id} | 200 | history:read |
| GET /runs/{id}/events | 200 | history:read |
| GET /conversations/{id}/history | 200 | history:read |
| GET /health | 200 | public |
| GET /ready | 200 or 503 | public |

Example requests (Authorization: Bearer local-alice in local fixture mode):

```http
POST /api/v1/shops/shop-a/orchestrator
Content-Type: application/json

{"template_id":"shopops","config_revision":"v1"}
```

```http
POST /api/v1/shops/shop-a/conversations
Content-Type: application/json

{"orchestrator_id":"<returned orchestrator_id>","client_conversation_id":"chat-1"}
```

```http
POST /api/v1/conversations/<conversation_id>/messages
Content-Type: application/json

{"client_message_id":"message-1","content":"Doanh thu tuần này thế nào?"}
```

```json
{"message_id":"<uuid>","run_id":"<uuid>","polling_url":"/api/v1/runs/<uuid>"}
```

Message content is trimmed to 1–8000 characters. Client identifiers are nonempty,
trimmed, and at most 128 characters. Extra request fields are rejected. Body bytes
are bounded at 65536 before JSON parsing (413 above limit), including chunked
requests. Query limit is 1–100/default 50. History/event cursors are UUID IDs;
syntactically invalid cursors return 422; the repository validates resource/scope
membership and orders by sequence. Follow `next_cursor` until null.

Errors use `{"error":{"code":"...","message":"Không thể xử lý yêu cầu.",
"retryable":false},"request_id":"<generated uuid>"}`. 403 permission_denied;
404 not_found; 409 configuration_conflict/idempotency_conflict/conversation_busy;
422 invalid_input/invalid_cursor; 503 not_ready (retryable=true). Unknown internal
exceptions return 500 internal_error without exception text. Validation errors do
not echo request contents. Readiness calls only the injected probe.

Run response contains run_id/status/validated response/error. History and events
project explicit public fields. Provider IDs, snapshots and raw errors are omitted;
unknown error codes become internal_error; unknown event types become status.
Public event tool names are allowlisted. No route invokes OpenAI or starts work.

## Integration gate

Route tests use an in-memory fake, establishing adapter behavior only. T01 must
verify real SQLite transactions for provisioning/conversation uniqueness, replay
before busy, payload conflicts and tenant/shop/owner isolation, then mount this
router with real readiness/auth configuration. T04 should align its synthetic IDs
with identities.json. Live JWT issuer connectivity is intentionally unverified.

## T05 runtime extension

`build_api_router` also accepts keyword-only `artifact_provider: AgentProvider | None`.
Messages accept optional `output_mode: text|report`, default text, with legacy report rejection
(422 invalid_input) and replay/conflict detection. Run response fields remain unchanged.
`GET /runs/{run_id}/artifacts` accepts the standard after/limit pagination, uses history:read
and returns items with local id, run_id, filename, media_type, size, sha256 and availability.
`GET /artifacts/{artifact_id}/content` resolves local scoped ownership before provider access;
foreign IDs are 404, unavailable content 410, invalid payload 502, transient I/O 503. Responses
use attachment disposition and nosniff; no provider redirect or user-selected path is accepted.
