# Capability map: mock data and synchronization MVP

Status: capability map and linked specifications approved by the user on
2026-10-31. Planning is authorized; implementation is pending plan approval.
See [implementation plan](tasks/plan.md) and [task checklist](tasks/todo.md).

| Module ID | Responsibility | Deployable service | Depends on | Specification |
|---|---|---|---|---|
| `mock-source` | Persistent synthetic source entities, CRUD, deterministic seeds, source snapshots | `mock-data-server` | None | [SPEC-mock-source.md](SPEC-mock-source.md) |
| `data-pipeline` | Full fetch, immutable raw evidence, normalized core upserts/deletions, calculated marts | `cronjob-server` | `mock-source` | [SPEC-data-pipeline.md](SPEC-data-pipeline.md) |
| `sync-control` | MCP-facing CRUD forwarding, manual/interval execution, run tracking, processed reads | `cronjob-server` | `mock-source`, `data-pipeline` | [SPEC-sync-control.md](SPEC-sync-control.md) |

Build order: `mock-source` -> `data-pipeline` -> `sync-control`. These are three
logical capabilities in two services, not three deployments.

## Confirmed requirements

- Python/FastAPI and PostgreSQL; service directories under `services/`.
- Ten active users identified only by canonical international phone strings.
  Merchants are active; some users have private merchants and others share.
- Twenty samples per user total across Shopee, Lazada, and Shopify, with related
  data covering the business scenarios. Exact seed interpretation appears below.
- CRUD and complete transformations are the MVP acceptance target. Existing
  anomaly thresholds need not all fire on the small dataset.
- A future MCP server calls `cronjob-server`, which forwards source CRUD to
  `mock-data-server`. It also provides processed core/mart reads.
- Successful mutations enqueue synchronization and return a run ID.
- Full synchronization; interval configured in seconds; manual API trigger.
- Explicit deletion records, reconciliation of dependent core records, retained
  historical raw evidence, and recalculated mart results.
- Scope: access tables/view, raw documents, eleven core tables, mart settings,
  and eight mart views including `agent_context`.
- Frozen business clock. Incident/action/approval/verification audit systems and
  the MCP server itself are outside this proposal.

## Approved design decisions

1. A sample means an order with related business records, not twenty rows in
   every table. Each user initially sees twenty distinct orders through access
   memberships. Shared orders are stored once. The approved seed has four
   individually owned merchants and three merchants shared by pairs: ten users,
   seven merchants, twenty-one shops, and 140 unique orders. Each merchant has
   seven Shopee, seven Lazada, and six Shopify orders. The twenty-order count is
   a seed invariant, not a limit enforced after CRUD.
2. Directory/deployment names use hyphens to satisfy `scripts/new-service.sh`:
   `services/mock-data-server/` and `services/cronjob-server/`. Python identifiers
   use underscores where appropriate.
3. Both services use the supplied database name `postgres` and username
   `postgres`, with independent schema ownership by application convention:
   `mock.*` for the source; `access.*`, `raw.*`, `core.*`, `mart.*`, `sync.*` for
   the processor. There are no cross-service SQL reads or foreign keys.
   Separate databases remain possible through independent connection settings.
4. APIs are private, trusted MCP/backend interfaces. `user_id` is a caller-supplied
   demo identity, not proof of authentication. All active merchant members may
   perform business CRUD in this MVP, irrespective of their descriptive role.
   Explicit administrative routes manage access entities. No login, OTP, user
   sessions, or production authorization system is introduced.
5. One global synchronization worker runs in a single process/replica, with a
   database lock preventing accidental overlapping application of snapshots.
   Each run synchronizes the full source dataset atomically. This is sufficient
   for the small MVP and avoids partially updated cross-table results.
6. Missing parent references reject writes with a conflict. Deleting an order
   cascades only to its items, reviews, returns, settlement, and fulfillment.
   Other referenced parents require their children to be removed first.

## Shared runtime and deployment contract

Both services follow `template/python-fastapi/AGENTS.md`, have `service.json`
with stack `python` and container port `8000`, and run the repository's `make ci`.
Use the existing Python 3.14 template and its pinned dependencies as the baseline.
Record exact new dependency versions during implementation, after compatibility
verification; do not invent version pins in these specs. A PostgreSQL driver is
required; no Redis, Celery, or separate scheduling service is required.

| Variable | Services | Contract |
|---|---|---|
| `POSTGRES_HOST` | Both | Required runtime host; not supplied yet |
| `POSTGRES_PORT` | Both | Default `5432` |
| `POSTGRES_USER` | Both | Runtime value `postgres` |
| `POSTGRES_PASSWORD` | Both | Required runtime secret; never checked into docs, fixtures, examples, or logs |
| `POSTGRES_DB` | Both | Runtime value `postgres` |
| `POSTGRES_SSLMODE` | Both | Explicit deployment choice; local example may use `disable` |
| `PORT` | Both | Default `8000` |
| `MOCK_DATA_SERVER_URL` | Cronjob | Required; fail startup if missing |
| `SYNC_INTERVAL_SECONDS` | Cronjob | Integer >= 0; default `0` disables periodic runs; positive value enables them |

Use a localhost example for the source URL. In CapRover it is
`http://srv-captain--mock-data-server-dev:8000` for dev and
`http://srv-captain--mock-data-server:8000` for production, supplied through App
Configs, never a code default. Both apps are internal with **Do not expose as web
app**, no public domains or Port Mapping. The future MCP service uses the same
cluster-network convention to reach `cronjob-server`.

Document every variable in each service's `.env.example` and README; examples
contain placeholders for secrets. Construct database connections from driver
parameters so special password characters are preserved. Credentials supplied in
conversation must not be reproduced. Existing production tables must not be
assumed disposable: initialization targets fresh dedicated demo schemas and
never drops unrelated data. No connection or deployment is part of this task.

## Existing sources of truth

- [Compact mock inputs](data_preparation/data_mock_raw_for_mock_server/README.md)
  supply representative source payloads and the phone identity convention.
- [Full data guide](data_preparation/data_mock_sample/README.md) and
  [dictionary](data_preparation/data_mock_sample/DATA-DICTIONARY.md) supply business
  meanings, entity fields, and scenario coverage.
- [Core schema](data_preparation/data_mock_sample/sql/001_schema.sql),
  [access view](data_preparation/data_mock_sample/sql/003_access.sql), and
  [mart views](data_preparation/data_mock_sample/mart/002_views.sql) define baseline
  keys, constraints, formulas, and thresholds.
- [Connector mappings](data_preparation/data_mock_sample/scripts/normalize.py)
  define the initial transformations. Runtime code must be adapted into the
  appropriate service, without imports from another service or dependencies on
  repository-root files in deployed containers.

## Review and operational questions

- The user approved the twenty-visible-orders layout above with the specifications.
- Before deployment, supply the PostgreSQL hostname, confirm its port/TLS mode,
  and confirm whether the target schemas are fresh. These do not block writing
  the specifications.
- No additional business decisions block planning. Changes to approved decisions
  should update the affected module spec before coding.
