# Spec: sync-control

Status: approved by the user on 2026-10-31. Module: `sync-control`. Lives in
`services/cronjob-server/`; depends on [mock-source](SPEC-mock-source.md) and
[data-pipeline](SPEC-data-pipeline.md). Shared decisions and deployment settings
are in [CAPABILITY-MAP.md](CAPABILITY-MAP.md).

## Objective

Give the future MCP server one HTTP interface for source CRUD, processed reads,
manual synchronization, and job status. Persist mutation/synchronization intent
so a restart cannot silently lose an accepted operation. Periodic execution is
configured by one interval in seconds. The MCP implementation, agent tools,
business audit trail, approval workflow, and notifications are outside scope.

## Tech stack and project structure

Use the same Python/FastAPI/PostgreSQL toolchain and service files defined by the
pipeline spec. `app/api/` owns Pydantic contracts and routes; `app/jobs/` owns the
single worker, interval loop, and recovery; `app/storage/` holds `sync` metadata.
Use an application lifecycle task and PostgreSQL-backed pending records; no cron
daemon, Redis, Celery, or new deployable service is required.

The minimal operational objects are `sync.runs`, persisted source-mutation
intents/receipts, and the pipeline's applied revision/deletion bookkeeping. They
contain identifiers, intent needed for safe recovery, progress, attempts,
timestamps, source revision, and bounded sanitized error codes. They are not an
incident, recommendation, approval, or execution-history product.

## Identity, access, and trust model

The MCP caller supplies the canonical phone string as `X-Demo-User-Id`; in MCP
tool arguments this remains `user_id`. This is an internal demo convention, not
verified authentication. All user-scoped routes resolve current access from the
source before reading/mutating business data. Source outages fail these requests
with `503`, rather than authorizing from stale replicated memberships.

Use the intersection of current source grants and processed merchant/shop
ownership for reads. Apply it to core, mart, raw evidence, and per-shop job counts.
Unknown callers receive `403`; inaccessible records receive `404`. Never accept
merchant ownership or roles from the caller as authorization. Active owner,
analyst, and viewer memberships all allow business CRUD for this demo.

Administrative routes intentionally trust the internal backend globally and are
separate from user-scoped tools. They support creating users/merchants/memberships,
global run inspection, and mart settings. A caller-supplied phone cannot make
these routes safe for public exposure; the deployment boundary is the private
cluster network. Do not add login/OTP/session features to this proposal.

## MCP-facing HTTP contract

Use `/v1`, `snake_case` JSON, the error envelope and pagination rules from the
source spec, and typed OpenAPI models. Reject unknown resources and unsupported
filter names. Each underlying entity gets concrete create/patch/response models.
Composite record keys are query parameters, avoiding path parsing problems for
Shopify IDs. The MCP server need not know SQL or access the source service itself.

| Route | Required behavior |
|---|---|
| `GET/POST /v1/mock/{resource}` | Forward scoped list/create to source business entities |
| `GET/PATCH/DELETE /v1/mock/{resource}/record?...` | Forward scoped single-record read/update/delete |
| `/v1/admin/mock/{resource}` and `/record?...` | Forward CRUD for users, merchants, memberships on explicit admin routes |
| `POST /v1/sync-runs` | Validate caller, persist and enqueue a full sync; `202` |
| `GET /v1/sync-runs` | Paginated runs requested by the caller, with current-access-filtered results |
| `GET /v1/sync-runs/{run_id}` | Caller-owned run status; counts/errors filtered as below |
| `GET /v1/admin/sync-runs` and `/{run_id}` | Global operational run inspection, including scheduled/admin runs |
| `GET /v1/core/{resource}` and `/record?...` | Scoped processed core lists and full-key lookup |
| `GET /v1/marts/{view}` | Scoped view rows, optional shop/window filters where applicable |
| `GET /v1/raw/documents` and `/record?document_id=...` | Scoped observed historical raw evidence |
| `GET /v1/access/shops` | Current allowed shops for the supplied phone identity |
| `GET/PATCH /v1/admin/mart-settings` | Read/update the singleton frozen clock and positive window lengths |
| `GET /health/live`, `GET /health/ready` | Process liveness; database/migration/worker readiness |

Core allowlist: all eleven tables from the pipeline spec, using the source API's
hyphenated resource names. Mart allowlist: its eight SQL view names. Reads include
`applied_source_revision` so callers can distinguish stale processed results from
current source reads. Raw/core/mart endpoints are read-only. Changing a business
record always goes through source CRUD and synchronization. Mart settings are a
singleton configuration, so create/delete are intentionally unsupported.

List responses use `data`, `pagination`, and revision metadata. Sort by stable
entity/view grain; filter by allowed `shop_key`, date window, and documented
resource-specific fields. Admin access CRUD uses the same source entity contracts.
No arbitrary relation, column, ordering expression, or SQL input is accepted.

User-scoped full synchronization fetches/processes the entire demo source; it does
not limit ingestion to the caller. Return only the caller's permitted per-shop
counts and generic global failure codes. Do not leak other merchants' IDs or data
in errors. Scheduled jobs and other users' job IDs are unavailable on user routes.
Admin routes can inspect global counts. Historical raw for a deleted shop remains
stored; user access requires a current grant, so retention does not grant new reads.

## Mutation and synchronization response

All writes, including manual triggers and settings changes, require
`Idempotency-Key`. Preserve it when forwarding a source mutation. Same caller/key
and request intent replay the original operation/run; changed intent returns
`409`. Retain receipts for the demo dataset lifetime. A response timeout does not
prove failure, and must not create a new mutation intent when retried.

For a confirmed source CRUD mutation, return `202` with its source result and
persisted run reference:

```json
{
  "data": { "shop_key": "shopee-open-platform:1001", "order_id": "100072" },
  "mutation_status": "applied",
  "source_revision": 12,
  "run_id": "<uuid>",
  "sync_status": "queued",
  "status_url": "/v1/sync-runs/<uuid>"
}
```

The example shows an abbreviated entity, not an alternate response schema.
`applied` refers only to the source mutation; processed results become current
when its run succeeds at revision >= 12. A deletion returns a deletion receipt
instead of the deleted row. Shared users see the changed source immediately and
the processed change after synchronization. Ordinary read requests do not enqueue.

Before contacting the source, commit a mutation intent with its stable run ID and
idempotency key locally. On source confirmation, atomically record its result and
minimum revision and mark the associated run queued. A worker recovers pending
intents by retrying the same source idempotency key; it must not report source
success before confirming the outcome. If the source outcome is uncertain, return
`202` with `mutation_status: pending`, `source_revision: null`, and the stable run
ID; its sync state remains `pending_mutation`. This closes the gap between a
successful source write and a processor crash before enqueueing.

Validation/access/reference conflicts return their source status and sanitized
error; persist the rejected intent without enqueueing a pipeline run. A confirmed
mutation is never rolled back merely because later synchronization fails. Its
run exposes that distinction and may be followed by a new manual full-sync run.
When a caller retries after an ambiguous timeout, the original operation remains
discoverable and safe to replay. Do not claim cross-service atomicity.

Manual `POST /v1/sync-runs` accepts an empty object; no delta filters or arbitrary
schedule payload. It persists the request and returns `202`, `run_id`, and
`status_url`. Mart-settings PATCH validates only `as_of`, `recent_days`, and
`baseline_days`, commits settings with its idempotency receipt, and returns `200`;
views recompute on read, so no source mutation or pipeline run is necessary.

## Run lifecycle, retries, and interval execution

Persist these run states: `pending_mutation`, `queued`, `running`, `succeeded`,
`failed`. Include trigger (`manual`, `mutation`, `interval`), requesting identity
where applicable, created/started/finished timestamps, attempt count,
minimum/applied source revision, per-shop entity counts, and sanitized error stage
and code. Source mutation status is tracked separately so a failed sync cannot be
mistaken for a rejected source write. No cancel endpoint is required for MVP.

- One worker serializes full runs. A PostgreSQL lock prevents overlapping apply
  operations even if a second process starts accidentally. Production scaling
  remains out of scope; deploy one replica and one application worker process.
- Configure `SYNC_INTERVAL_SECONDS` once at startup: `0` disables periodic
  scheduling, a positive integer enables it, invalid/negative values fail startup.
  No cron expression, per-shop schedule, timezone schedule, or schedule CRUD.
- When enabled, startup first recovers accepted work and enqueues a full run if
  there is no pending/running work. After the queue drains, wait N real seconds
  before the next interval run. Long jobs do not cause a backlog of missed ticks.
  Manual/mutation work can arrive during this wait and wakes the worker.
- Manual/mutation requests retain their own run IDs. If a later queued job's
  required revision is already applied, it succeeds as a verified no-op. New
  source mutations committed during an earlier snapshot require a subsequent run.
- Recover queued/pending work on restart. A previously running job is retried only
  after acquiring the global lock; inspect its applied marker before repeating
  publication. Database transactions and immutable documents make replay safe.
- Use bounded HTTP timeouts (proposed connect 5 seconds, read 30 seconds) and at
  most three automatic attempts per transient source/network/transaction failure,
  with 1-second then 2-second backoff. Do not automatically retry validation,
  incompatible schema, or reference errors.
- If mutation retries exhaust while source outcome is still unknown, mark the run
  failed with `SOURCE_OUTCOME_UNKNOWN` and preserve the intent/key. Replaying the
  same caller request may explicitly resume reconciliation of that same intent;
  never report it as definitely unapplied. No blind new-key retry is safe.
- Database outages must not produce an acknowledgement for an unpersisted job.
  Readiness reflects database/worker availability. Source outages appear in
  relevant requests/run results; liveness does not restart a healthy process just
  because the source is temporarily unavailable.

Scheduling and job timestamps use real UTC time. Business event times and mart
evaluation use the frozen clock. Create/patch models document required event-time
fields. Where a convenience default is offered for a new order, use
`ordered_at = as_of - 1 second` and `updated_at = as_of`; do not move the mart clock
or silently use the actual date. Explicit future dates remain valid where the
entity's domain permits and can be excluded by mart windows as documented.

## Commands and API example

Required future service commands from `services/cronjob-server/` in POSIX/WSL:

```sh
make install
.venv/bin/python -m app.cli migrate
make run
make ci
.venv/bin/pytest tests -q
docker build -t cronjob-server .
```

Example manual trigger once the service is running locally; local host port 8001
is separate from the source service's 8000, while both container ports are 8000:

```sh
curl --request POST http://localhost:8001/v1/sync-runs \
  --header 'Content-Type: application/json' \
  --header 'X-Demo-User-Id: +84900000001' \
  --header 'Idempotency-Key: demo-manual-sync-001' \
  --data '{}'
```

To run both locally, override the processor command explicitly:
`.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001`.
Service READMEs must include encoded composite-key CRUD examples and run polling.
No live requests or deployments are made while writing this specification.

## Code style

Use typed request/response models, concise route handlers, parameterized queries,
template Ruff formatting, and explicit enum states. Do not start a process-local
untracked background task as the only record of accepted work. Example response
model style:

```python
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class RunAccepted(BaseModel):
    run_id: UUID
    sync_status: Literal["queued"]
    status_url: str
```

Log run ID, stage, safe counts, timings, and error codes. Do not log phone IDs,
raw request bodies, source payloads, connection strings, or secrets. Persisted
intent bodies are needed for recovery and remain internal data, not log output.

## Testing strategy and success criteria

Use pytest with FastAPI TestClient for routing/contracts and real PostgreSQL for
queue persistence, idempotency, and locks. End-to-end tests run both service apps
with HTTP communication and isolated database schemas. Control the scheduler's
clock in tests rather than sleeping through long intervals. No additional
percentage coverage threshold is imposed.

- Every business/admin resource completes a CRUD round trip through the facade;
  the facade never writes the source's tables directly.
- Create/update/delete returns a stable run ID. Polling reaches success and
  processed core/mart reads demonstrate the correct effect and source revision.
- A source commit followed by a simulated processor crash is recovered with one
  mutation effect and a completed synchronization; ambiguous outcomes are explicit.
- Full synchronization is triggerable manually with periodic execution disabled.
  Positive intervals run repeatedly without overlap or accumulating missed ticks.
- Jobs/intents survive restart. A run committed before interruption is recognized
  as already applied; source mutations during a run are reflected by the next run.
- Three transient attempts then failure are visible; validation failures are not
  retried; retrying a stable intent does not generate duplicate effects.
- Reads and writes are scoped by current membership. Shared users see the same
  records, unrelated users cannot read them, and deleting membership denies the
  next request before the next data synchronization.
- Raw/core/mart list/query responses and run status do not leak other merchants'
  data. Source outages fail closed on user-scoped requests.
- Frozen business time does not advance when the interval runs. Real operational
  timestamps do advance. Settings edits change calculated windows deliberately.
- Startup configuration validates required source/database settings and negative
  intervals; health and sanitized errors identify unavailable dependencies.

## Boundaries and open questions

- Always: record intent before forwarding writes, honor idempotency, validate and
  scope user requests, expose eventual-consistency status, and run `make ci`.
- Ask first: adding production authentication, public exposure, distributed
  workers, per-user schedules, or incident/action audit features.
- Never: treat phone input as verified login, acknowledge an unpersisted job,
  fabricate sync success after a timeout, allow arbitrary SQL, or embed secrets.

No additional API/scheduling question blocks planning. The capability map
records the approved seed layout and outstanding deployment host/TLS inputs.
