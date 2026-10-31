# Shop Data MCP integration handoff

Updated 2026-10-31. This service implements the MCP side of the boundary. The ingestion,
processing, identity and raw-approval services are external dependencies; their contracts
below are proposed for their engineers to implement. They are not deployed or verified
integrations. An unconfigured or failed dependency returns an error; there is no fixture
fallback or automatic approval.

## Service configuration and identity

The operator supplies the JSON configuration referenced by `MCP_CONFIG_FILE`; see
`app/settings.py` for the authoritative schema. Keep real credentials outside source
control. Resolve actual service names and use their private cluster origins
`http://srv-captain--<app-name>:<port>`; browser-facing public domains are not upstream
addresses. Each adapter accepts an origin only, without credentials, path, query or
fragment. Local integration tests can use a local origin.

The identity engineer must provision the trusted RS256 issuer and audience, verification
keys, token renewal/revocation and verified owner-to-shop membership. MCP authorization
scopes are `data:read`, `raw:request`, `raw:read` and `data:refresh`. The verified token
supplies `sub` (mapped to subject) and `shop_key`; tool arguments cannot choose another shop or identity.
Service-to-service authentication uses a separately configured service bearer credential.
The caller's MCP bearer token is never forwarded to an upstream.

## Common HTTP requirements

Every endpoint below requires `Authorization: Bearer <service credential>`, and returns
a JSON object. The upstream authenticates the service and authorizes the asserted shop
and subject. It must not treat an arbitrary caller-supplied shop header as authorization.
Use stable opaque identifiers matching `[A-Za-z0-9_-]{1,128}`. All timestamps are ISO 8601
with an explicit timezone; ranges use inclusive `start` and exclusive `end` in UTC.

The MCP adapter accepts 2xx responses only, disables redirects and environment proxies,
and performs one HTTP attempt. It applies a 15-second total deadline, a 5-second connect
timeout and a 1 MiB decoded response limit. Return uncompressed JSON: the adapter requests
`Accept-Encoding: identity` and rejects compressed responses. A status error, invalid JSON,
oversized response or network failure produces a fixed sanitized integration error. Never
return raw payloads, credentials or personal data in error messages or operation metadata.
The caller validates response fields and ownership after transport validation. Approval and
operation response objects reject unknown fields, including unknown coverage fields, instead
of relaying arbitrary upstream JSON.

## Collection and processing API

The collection engineer must expose `POST /v1/refreshes` and `GET /v1/operations/{id}`.
The collection service owns orchestration of processing, or the engineers must agree an
equivalent coordinator before enabling refresh. The MCP does not infer completion from
successful collection or submit an untracked processing job.

`POST /v1/refreshes` accepts exactly this proposed request shape:

```json
{
  "subject": "agent-subject",
  "shop_key": "shop-key",
  "resource": "orders",
  "start": "2026-10-01T00:00:00Z",
  "end": "2026-10-02T00:00:00Z",
  "idempotency_key": "refresh-request-key"
}
```

`resource` must identify an allowed collection resource, never an arbitrary URL or SQL
statement. The MCP applies its resource/lookback and cooldown policy before submission;
the upstream must also enforce its operational budgets and shop access. The upstream must
persist idempotency before starting work. A repeat key with the same subject, shop and
canonical payload returns the same operation; a reused key with a different payload fails
with `409`. Retain keys for at least the full operation lifetime and the agreed retry window.
The exact retention window remains an integration decision. A network failure can occur
after work was accepted: retry only with the same idempotency key after reconciliation.

Return `202` for a newly accepted operation, or `200` for a deduplicated operation:

```json
{"operation_id":"operation-key","status":"queued"}
```

`GET /v1/operations/{operation_id}?subject=<subject>&shop_key=<shop_key>` returns `200`:

```json
{
  "operation_id": "operation-key",
  "subject": "agent-subject",
  "shop_key": "shop-key",
  "status": "processing",
  "coverage": {
    "dataset_ids": ["orders"],
    "start": "2026-10-01T00:00:00Z",
    "end": "2026-10-02T00:00:00Z",
    "collection_completed_at": "2026-10-02T00:01:00Z",
    "processing_completed_at": null
  },
  "error_code": null
}
```

Allowed statuses: `queued`, `collecting`, `raw_available`, `processing`, `mart_ready`,
`failed`, `cancelled`, `partial`. `raw_available` means collection succeeded; it does not
authorize raw disclosure. Only `mart_ready` means the requested interval/resource has
completed processing and the corresponding analytical data is committed and visible.
`partial` must never be presented as fresh complete coverage. `coverage` may be null; when
present it contains exactly `dataset_ids` (at most 100 identifiers matching
`[a-z][a-z0-9_]{0,62}`), required timezone-aware `start` and `end`, and optional nullable
timezone-aware `collection_completed_at` and `processing_completed_at`. Arbitrary text and
naive timestamps are rejected. Optional nullable `error_code` must match `[A-Z0-9_]{1,64}`.
Unknown response or coverage fields are rejected. Before live rollout, agree the source
catalog's freshness update mechanism so status and actual queryable coverage cannot disagree.
Unknown or inaccessible operations return
`404`; the MCP also checks its locally persisted operation owner before polling.

## Raw-access owner approval API

The approval engineer must implement a trusted owner approval flow, not an agent-callable
approval action. The MCP may create a request; only the verified owner can approve it.

`POST /v1/raw-access-requests` accepts:

```json
{
  "subject": "agent-subject",
  "shop_key": "shop-key",
  "datasets": {"raw_orders": ["order_id", "status"]},
  "start": "2026-10-01T00:00:00Z",
  "end": "2026-10-02T00:00:00Z",
  "reason": "Investigate the discrepancy in processed order counts"
}
```

The approval service validates requested datasets, columns, time bounds and shop ownership.
Return `202` with `{"request_id":"request-key","status":"pending"}`. Only `request_id`
and `status` are accepted; status must be `pending` or `denied`. Unknown response fields
are rejected. A successful request creation is not a grant. The owner interface must
authenticate the owner, present exact scope and expiry,
record the decision and supply the approved grant identifier through a trusted product flow.
Grant delivery/callback authentication and request deduplication remain integration decisions.
The adapter does not retry this POST automatically.

`GET /v1/grants/{grant_id}?subject=<subject>&shop_key=<shop_key>` returns `200` for a grant
visible to that subject/shop:

```json
{
  "grant_id": "grant-key",
  "subject": "agent-subject",
  "shop_key": "shop-key",
  "status": "approved",
  "expires_at": "2026-10-31T11:00:00Z",
  "datasets": {"raw_orders": ["order_id", "status"]},
  "start": "2026-10-01T00:00:00Z",
  "end": "2026-10-02T00:00:00Z"
}
```

Only `status: approved` with an unexpired timestamp and matching grant/subject/shop is
usable. Pending, denied, revoked, expired, unknown or unreachable grants fail closed.
Return `404` for unknown or inaccessible grants. Do not cache away revocation: query and
raw-derived mart access must revalidate authorization. Temporary marts inherit the approved
datasets/columns/time bounds and cannot outlive the grant. Grant responses are immutable: issue a new grant ID to change or renew scope. Saved results compare their original grant response on every read; a changed response denies access. Define revocation propagation and
owner identity audit evidence before enabling raw access.

## Database and release prerequisites

The database engineer must provide restricted control metadata, shop-bound execution roles and a restricted control/workspace writer, enforce RLS and supply the approved source catalog and column/time
projections. Do not replace the shop-bound resolver with an unrestricted shared login.
Apply migrations through an operator credential, verify private routing and verified TLS,
and test shop isolation across repeated query connections.

Before accepting external agent traffic, verify real issuer/revocation behavior, missing
configuration failures, cross-shop access denials, raw approval/expiry/revocation, refresh
deduplication, partial processing, coverage freshness and sanitized upstream failures.
Adapter tests with MockTransport validate HTTP behavior only. They do not demonstrate
working upstream services, PostgreSQL isolation or a live deployment. Follow the owning
[configuration guide](../../docs/shop-data-mcp-configuration.md) for topology and release checks.

Unresolved: actual upstream service identities and credentials; issuer and revocation
contract; owner approval callback; upstream idempotency retention; source freshness/watermark updates;
approved database schema/catalog and role provisioning; live end-to-end verification.
