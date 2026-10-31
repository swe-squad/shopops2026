# Task checklist: mock data and synchronization MVP

Status: plan/checklist approved by the user on 2026-10-31. Implementation is in
progress. Specifications are approved. Read [plan.md](plan.md) and the linked
module specifications before executing a task.

## Conventions

- Source = `services/mock-data-server/`; processor =
  `services/cronjob-server/`. Commands state their working directory.
- Task IDs are stable. Dependencies must be completed before a task begins;
  execute in numeric order by default.
- Bootstrap tasks reuse portions of the existing Python/shared templates so no
  single task hides an oversized generated patch.
- File lists are concrete anticipated paths, not permission to ignore an extra
  change. Split a task before expanding beyond five substantive files.
- `make test TEST_ARGS="..."` runs pytest through the isolated PostgreSQL harness
  after task 06 (source) or task 25 (processor). Earlier commands explicitly state
  their setup prerequisites. These commands/files are planned interfaces.
- Acceptance must be tested at the observable boundary. Record command/results
  in Evidence; keep failed/incomplete tasks unchecked. No failing tests may be
  skipped, removed, or weakened to pass a checkpoint.
- Checkpoints are verification milestones, not extra permission gates after
  implementation is authorized. Material scope changes still require review.
- Service-local `AGENTS.md` applies as soon as created. Before code work, use the
  applicable implementation/git/testing skills; commits use a required service
  or shared-area scope. This checklist does not authorize merge or deployment.

### T01: Source runtime template

- [x] Complete T01.

**Module:** `mock-source`. **Dependencies:** None. **Scope:** M (4 files).

**Acceptance:**

- Copy the existing Python runtime and health-test template with the source service name; preserve its app-factory convention.
- No database connection or automatic seed runs on import.

**Verify:** From source: `python -m compileall -q app tests`; run the copied health test after task 02 installs dependencies.

**Likely files:** `services/mock-data-server/app/__init__.py`, `services/mock-data-server/app/main.py`, `services/mock-data-server/tests/__init__.py`, `services/mock-data-server/tests/test_health.py`.

**Evidence:** Python 3.14.5; native Windows pytest/ruff equivalents passed. Source foundation suite: 9 passed against disposable PostgreSQL 17. Template image build succeeded. Docker port readiness race diagnosed and guarded.

### T02: Source build toolchain

- [x] Complete T02.

**Module:** `mock-source`. **Dependencies:** T01. **Scope:** M (5 files).

**Acceptance:**

- Reuse the template's pinned toolchain and Python version; standard install/lint/test/build commands work.
- Image contains the runtime app and listens on container port 8000.

**Verify:** From source: `make ci` and `docker build -t mock-data-server .`; the copied health test passes.

**Likely files:** `services/mock-data-server/requirements.txt`, `services/mock-data-server/requirements-dev.txt`, `services/mock-data-server/pyproject.toml`, `services/mock-data-server/Makefile`, `services/mock-data-server/Dockerfile`.

**Evidence:** Python 3.14.5; native Windows pytest/ruff equivalents passed. Source foundation suite: 9 passed against disposable PostgreSQL 17. Template image build succeeded. Docker port readiness race diagnosed and guarded.

### T03: Source service metadata

- [x] Complete T03.

**Module:** `mock-source`. **Dependencies:** T02. **Scope:** M (5 files).

**Acceptance:**

- Metadata matches the repository scaffolder: stack python, port 8000, service name mock-data-server.
- Document future environment inputs with secret placeholders and the internal-service boundary.

**Verify:** From source: `python -m json.tool service.json` and `python -m json.tool captain-definition`; compare metadata and substituted template names with `scripts/new-service.sh`.

**Likely files:** `services/mock-data-server/AGENTS.md`, `services/mock-data-server/service.json`, `services/mock-data-server/captain-definition`, `services/mock-data-server/README.md`, `services/mock-data-server/.env.example`.

**Evidence:** Python 3.14.5; native Windows pytest/ruff equivalents passed. Source foundation suite: 9 passed against disposable PostgreSQL 17. Template image build succeeded. Docker port readiness race diagnosed and guarded.

#### Checkpoint after T03

- [ ] Source template is runnable and its service metadata matches the repository convention.
- [ ] Use task 02 health/CI/image evidence; confirm no real database credentials entered the tree.

### T04: Source database configuration

- [x] Complete T04.

**Module:** `mock-source`. **Dependencies:** T03. **Scope:** M (5 files).

**Acceptance:**

- Validate required PostgreSQL settings without printing credentials; preserve special password characters.
- Verify and pin a Python-3.14-compatible PostgreSQL driver from official documentation; keep blocking I/O off async handlers.

**Verify:** From source: `make install` then `.venv/bin/pytest tests/test_config.py -q`; database connection coverage follows in task 06.

**Likely files:** `services/mock-data-server/app/config.py`, `services/mock-data-server/app/storage/db.py`, `services/mock-data-server/requirements.txt`, `services/mock-data-server/tests/test_config.py`, `services/mock-data-server/.env.example`.

**Evidence:** Python 3.14.5; native Windows pytest/ruff equivalents passed. Source foundation suite: 9 passed against disposable PostgreSQL 17. Template image build succeeded. Docker port readiness race diagnosed and guarded.

### T05: Source migrations

- [x] Complete T05.

**Module:** `mock-source`. **Dependencies:** T04. **Scope:** M (5 files).

**Acceptance:**

- Versioned migrate command initializes owned access/source-revision structures without touching unrelated schemas.
- Migrations replay safely; phone equality/format, membership keys, and active flags match the source contract.

**Verify:** With an explicitly isolated test PostgreSQL target: `.venv/bin/pytest tests/test_migrations.py -q`; task 06 makes provisioning automatic.

**Likely files:** `services/mock-data-server/app/cli.py`, `services/mock-data-server/app/storage/migrations.py`, `services/mock-data-server/app/migrations/001_access.sql`, `services/mock-data-server/tests/test_migrations.py`, `services/mock-data-server/tests/conftest.py`.

**Evidence:** Python 3.14.5; native Windows pytest/ruff equivalents passed. Source foundation suite: 9 passed against disposable PostgreSQL 17. Template image build succeeded. Docker port readiness race diagnosed and guarded.

### T06: Source PostgreSQL test runner

- [x] Complete T06.

**Module:** `mock-source`. **Dependencies:** T05. **Scope:** M (5 files).

**Acceptance:**

- make test/make ci provision or validate an isolated real PostgreSQL target; missing prerequisites fail rather than skip tests.
- Cleanup touches only harness-created resources; TEST_ARGS selects focused tests; no demo credentials are used.

**Verify:** From source: `make test TEST_ARGS="tests/test_config.py tests/test_migrations.py -q"`; deliberately unsafe target is rejected before migrations.

**Likely files:** `services/mock-data-server/scripts/test_db.py`, `services/mock-data-server/Makefile`, `services/mock-data-server/tests/conftest.py`, `services/mock-data-server/requirements-dev.txt`, `services/mock-data-server/README.md`.

**Evidence:** Python 3.14.5; native Windows pytest/ruff equivalents passed. Source foundation suite: 9 passed against disposable PostgreSQL 17. Template image build succeeded. Docker port readiness race diagnosed and guarded.

#### Checkpoint after T06

- [ ] Source config, migration replay, and isolated PostgreSQL harness pass together.
- [ ] Run source `make ci`; unsafe target and missing-database prerequisites fail visibly.

### T07: Atomic source mutation receipts

- [x] Complete T07.

**Module:** `mock-source`. **Dependencies:** T06. **Scope:** M (5 files).

**Acceptance:**

- Persist idempotency claim, intent hash, mutation result, and monotonic revision atomically; same intent replays once.
- Changed intent conflicts, in-flight duplicates are retryable, failed writes roll back, and errors use the approved envelope.

**Verify:** From source: `make test TEST_ARGS="tests/test_mutations.py -q"`; include concurrent same-key attempts and a forced transaction failure.

**Likely files:** `services/mock-data-server/app/storage/mutations.py`, `services/mock-data-server/app/migrations/002_mutations.sql`, `services/mock-data-server/app/api/common.py`, `services/mock-data-server/app/main.py`, `services/mock-data-server/tests/test_mutations.py`.

**Evidence:** Python 3.14.5; native Windows pytest/ruff equivalents passed. Source foundation suite: 9 passed against disposable PostgreSQL 17. Template image build succeeded. Docker port readiness race diagnosed and guarded.

### T08: Access administration

- [x] Complete T08.

**Module:** `mock-source`. **Dependencies:** T07. **Scope:** M (5 files).

**Acceptance:**

- Implement typed admin CRUD for users, merchants, memberships and the current-access lookup with phone IDs.
- Membership changes affect access immediately; referenced parents reject deletion; shared membership returns shared shop grants as shops are added.

**Verify:** From source: `make test TEST_ARGS="tests/test_access.py -q"`; test phone encoding, duplicate keys, deleted identities, and rejected references.

**Likely files:** `services/mock-data-server/app/api/access.py`, `services/mock-data-server/app/domain/access.py`, `services/mock-data-server/app/storage/access.py`, `services/mock-data-server/app/main.py`, `services/mock-data-server/tests/test_access.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

### T09: Shop CRUD

- [x] Complete T09.

**Module:** `mock-source`. **Dependencies:** T08. **Scope:** M (5 files).

**Acceptance:**

- Shop create/list/read/patch/delete enforces membership, platform-qualified keys, immutable ownership, and source receipts.
- OpenAPI has concrete shop models; unknown/inaccessible records follow 403/404 rules.

**Verify:** From source: `make test TEST_ARGS="tests/test_shops.py -q"`; include two platforms with the same source shop ID.

**Likely files:** `services/mock-data-server/app/api/entities.py`, `services/mock-data-server/app/domain/shops.py`, `services/mock-data-server/app/migrations/003_shops.sql`, `services/mock-data-server/app/main.py`, `services/mock-data-server/tests/test_shops.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

#### Checkpoint after T09

- [ ] Access/shops operate over HTTP with phone identity, membership scope and atomic mutation receipts.
- [ ] Run source `make ci`; include shared membership and concurrent retry evidence.

### T10: Products and promotions

- [x] Complete T10.

**Module:** `mock-source`. **Dependencies:** T09. **Scope:** M (5 files).

**Acceptance:**

- Typed product/promotion CRUD preserves decimal/null values, funding, date ranges, and shop scope.
- Duplicate keys and referenced-parent deletion conflict; input extras and cross-shop references are rejected.

**Verify:** From source: `make test TEST_ARGS="tests/test_catalog.py -q"`.

**Likely files:** `services/mock-data-server/app/api/entities.py`, `services/mock-data-server/app/domain/catalog.py`, `services/mock-data-server/app/migrations/004_catalog.sql`, `services/mock-data-server/app/storage/catalog.py`, `services/mock-data-server/tests/test_catalog.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

### T11: Orders and order items

- [x] Complete T11.

**Module:** `mock-source`. **Dependencies:** T10. **Scope:** M (5 files).

**Acceptance:**

- Typed order/item CRUD preserves native IDs/status fields and platform-specific line grain; all foreign references remain in the same shop.
- Creation/update times use explicit or documented frozen-clock defaults; item changes maintain a coherent parent status and affected resource revisions.

**Verify:** From source: `make test TEST_ARGS="tests/test_orders.py -q"`; include Shopify global IDs, Lazada mixed status, and Shopee quantity.

**Likely files:** `services/mock-data-server/app/api/entities.py`, `services/mock-data-server/app/domain/orders.py`, `services/mock-data-server/app/migrations/005_orders.sql`, `services/mock-data-server/app/storage/orders.py`, `services/mock-data-server/tests/test_orders.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

### T12: Reviews and returns

- [x] Complete T12.

**Module:** `mock-source`. **Dependencies:** T11. **Scope:** M (5 files).

**Acceptance:**

- Review/return CRUD validates order/product references, ratings, event times, and refund amounts.
- Updates preserve omitted fields and allow null only where declared; actor membership scopes every operation.

**Verify:** From source: `make test TEST_ARGS="tests/test_feedback.py -q"`.

**Likely files:** `services/mock-data-server/app/api/entities.py`, `services/mock-data-server/app/domain/feedback.py`, `services/mock-data-server/app/migrations/006_feedback.sql`, `services/mock-data-server/app/storage/feedback.py`, `services/mock-data-server/tests/test_feedback.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

#### Checkpoint after T12

- [ ] Catalog, orders/items, reviews/returns meet typed CRUD and same-shop reference rules.
- [ ] Run source `make ci`; preserve money strings and encoded Shopify identifiers.

### T13: Inventory CRUD

- [x] Complete T13.

**Module:** `mock-source`. **Dependencies:** T11. **Scope:** M (5 files).

**Acceptance:**

- Inventory uses the full shop/SKU/location/observation-time key and supports encoded lookup and immutable keys.
- Null stock remains unknown; negative stock and cross-shop product references are rejected.

**Verify:** From source: `make test TEST_ARGS="tests/test_inventory.py -q"`; include two locations and two observation times.

**Likely files:** `services/mock-data-server/app/api/entities.py`, `services/mock-data-server/app/domain/inventory.py`, `services/mock-data-server/app/migrations/007_inventory.sql`, `services/mock-data-server/app/storage/inventory.py`, `services/mock-data-server/tests/test_inventory.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

### T14: Operational business entities

- [x] Complete T14.

**Module:** `mock-source`. **Dependencies:** T11. **Scope:** M (5 files).

**Acceptance:**

- Settlements, fulfillment, and account-health CRUD cover the remaining entities with typed models and source receipts.
- Cumulative money/null semantics, shipping dates, penalty intervals, and unsupported Shopify health behavior match the specification.

**Verify:** From source: `make test TEST_ARGS="tests/test_operations.py -q"`; validate every method for each of the three resources.

**Likely files:** `services/mock-data-server/app/api/entities.py`, `services/mock-data-server/app/domain/operations.py`, `services/mock-data-server/app/migrations/008_operations.sql`, `services/mock-data-server/app/storage/operations.py`, `services/mock-data-server/tests/test_operations.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

#### Checkpoint after T14

- [ ] Every source business entity has typed CRUD validation and complete key coverage.
- [ ] Run source `make ci`; confirm unsupported Shopify health and nullable inventory/finance cases.

### T15: Shopee and supplement serialization

- [x] Complete T15.

**Module:** `mock-source`. **Dependencies:** T12, T13, T14. **Scope:** M (4 files).

**Acceptance:**

- Canonical source orders/items serialize to the existing provisional Shopee shape without losing IDs, status, price, or quantity.
- Supplements represent all other business entities, order enrichment, shop metadata, and nullable values.

**Verify:** From source: `make test TEST_ARGS="tests/test_serialize_shopee.py tests/test_supplement.py -q"`.

**Likely files:** `services/mock-data-server/app/domain/serialize_shopee.py`, `services/mock-data-server/app/domain/serialize_supplement.py`, `services/mock-data-server/tests/test_serialize_shopee.py`, `services/mock-data-server/tests/test_supplement.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

### T16: Lazada serialization

- [x] Complete T16.

**Module:** `mock-source`. **Dependencies:** T15. **Scope:** S (2 files).

**Acceptance:**

- Serialize orders plus separate per-unit item response bundles with stable unit identifiers.
- Seller/platform vouchers, offset timestamps, and mixed item status survive round trips against fixture expectations.

**Verify:** From source: `make test TEST_ARGS="tests/test_serialize_lazada.py -q"`.

**Likely files:** `services/mock-data-server/app/domain/serialize_lazada.py`, `services/mock-data-server/tests/test_serialize_lazada.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

### T17: Shopify serialization

- [x] Complete T17.

**Module:** `mock-source`. **Dependencies:** T15. **Scope:** S (2 files).

**Acceptance:**

- Serialize GraphQL-shaped order nodes/line nodes preserving full global IDs, money strings, and quantities.
- Cancellation precedence and shipped-not-delivered semantics remain explicit; no health records are fabricated.

**Verify:** From source: `make test TEST_ARGS="tests/test_serialize_shopify.py -q"`.

**Likely files:** `services/mock-data-server/app/domain/serialize_shopify.py`, `services/mock-data-server/tests/test_serialize_shopify.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

#### Checkpoint after T17

- [ ] All three platform serializers plus supplements preserve approved native shapes.
- [ ] Run the source serialization suites; no missing resource fields or invented marketplace semantics.

### T18: Consistent versioned snapshot endpoint

- [x] Complete T18.

**Module:** `mock-source`. **Dependencies:** T16, T17. **Scope:** M (5 files).

**Acceptance:**

- GET snapshot returns complete access/documents/tombstones/counts at one source revision from a consistent database read.
- Unchanged resource versions retain IDs/content; changes update all affected representations atomically; incomplete exports fail.

**Verify:** From source: `make test TEST_ARGS="tests/test_snapshot.py -q"`; mutate concurrently with export and verify coherent counts/references.

**Likely files:** `services/mock-data-server/app/api/snapshot.py`, `services/mock-data-server/app/storage/snapshot.py`, `services/mock-data-server/app/domain/snapshot.py`, `services/mock-data-server/app/main.py`, `services/mock-data-server/tests/test_snapshot.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

### T19: Explicit deletion reconciliation at source

- [x] Complete T19.

**Module:** `mock-source`. **Dependencies:** T18. **Scope:** M (5 files).

**Acceptance:**

- Order deletion records all specified dependent tombstones in one transaction; deleting other live referenced parents returns 409.
- Deletion markers retain complete keys/ownership; deleted keys are reserved and retained access identities become inactive.

**Verify:** From source: `make test TEST_ARGS="tests/test_deletions.py -q"`; verify snapshot markers, retry behavior, failed-delete rollback, and key reservation.

**Likely files:** `services/mock-data-server/app/storage/tombstones.py`, `services/mock-data-server/app/storage/orders.py`, `services/mock-data-server/app/storage/mutations.py`, `services/mock-data-server/app/migrations/009_tombstones.sql`, `services/mock-data-server/tests/test_deletions.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

### T20: Deterministic MVP seed

- [x] Complete T20.

**Module:** `mock-source`. **Dependencies:** T19. **Scope:** M (5 files).

**Acceptance:**

- Seed has exactly 10 active phone users, 7 merchants, 21 shops, 140 unique orders and 20 distinct visible orders per user, with 7/7/6 platform split.
- Manifest covers all approved business scenarios/entities; repeated explicit seeding preserves edits and startup never reseeds.

**Verify:** From source: `make test TEST_ARGS="tests/test_seed.py -q"`; migrate/seed a fresh test database twice, edit a seeded row, and verify replay preserves it.

**Likely files:** `services/mock-data-server/app/fixtures/mvp.py`, `services/mock-data-server/app/fixtures/scenarios.json`, `services/mock-data-server/app/storage/seed.py`, `services/mock-data-server/app/cli.py`, `services/mock-data-server/tests/test_seed.py`.

**Evidence:** Source suite: 36 passed on disposable PostgreSQL 17; Ruff check/format passed; service-only Docker build succeeded. Covers all entity CRUD, native serializers, stable document versions, explicit deletion markers, replay authorization, and exact 10/7/21/140 seed counts. Related models/routes consolidated into domain/entities.py, api/entities.py and storage/entities.py; focused cases live in the corresponding source tests.

#### Checkpoint after T20

- [ ] Source module meets seed, snapshot consistency, deletion and retry acceptance criteria.
- [ ] Run source `make ci` and rebuild its image; assert exact seed visibility/counts and replay after edits.

### T21: Processor runtime template

- [ ] Complete T21.

**Module:** `data-pipeline`. **Dependencies:** T20. **Scope:** M (4 files).

**Acceptance:**

- Copy the existing application/health template using cronjob-server naming; no source or database side effects on import.

**Verify:** From processor: `python -m compileall -q app tests`; execute health tests after task 22.

**Likely files:** `services/cronjob-server/app/__init__.py`, `services/cronjob-server/app/main.py`, `services/cronjob-server/tests/__init__.py`, `services/cronjob-server/tests/test_health.py`.

**Evidence:** Pending implementation.

### T22: Processor build toolchain

- [ ] Complete T22.

**Module:** `data-pipeline`. **Dependencies:** T21. **Scope:** M (5 files).

**Acceptance:**

- Template install/lint/test/build interfaces work with pinned baseline dependencies.
- Docker build uses only this service directory and contains the app on port 8000.

**Verify:** From processor: `make ci` and `docker build -t cronjob-server .`.

**Likely files:** `services/cronjob-server/requirements.txt`, `services/cronjob-server/requirements-dev.txt`, `services/cronjob-server/pyproject.toml`, `services/cronjob-server/Makefile`, `services/cronjob-server/Dockerfile`.

**Evidence:** Pending implementation.

### T23: Processor service metadata

- [ ] Complete T23.

**Module:** `data-pipeline`. **Dependencies:** T22. **Scope:** M (5 files).

**Acceptance:**

- Metadata matches repository conventions and documents MOCK_DATA_SERVER_URL, PostgreSQL inputs and interval settings.
- Document localhost source URL, distinct local ports, internal CapRover routing, and secret placeholders.

**Verify:** From processor: `python -m json.tool service.json` and `python -m json.tool captain-definition`; inspect template substitutions and env-variable coverage.

**Likely files:** `services/cronjob-server/AGENTS.md`, `services/cronjob-server/service.json`, `services/cronjob-server/captain-definition`, `services/cronjob-server/README.md`, `services/cronjob-server/.env.example`.

**Evidence:** Pending implementation.

#### Checkpoint after T23

- [ ] Processor template and service metadata match the repository convention.
- [ ] Use task 22 health/CI/image evidence and inspect its internal URL/environment examples.

### T24: Processor runtime configuration

- [ ] Complete T24.

**Module:** `data-pipeline`. **Dependencies:** T23. **Scope:** M (5 files).

**Acceptance:**

- Source URL/database settings fail fast when required values are missing; interval is an integer >= 0.
- Pin the verified PostgreSQL driver and runtime HTTP client; preserve driver parameter handling without credential logging.

**Verify:** From processor: `make install` then `.venv/bin/pytest tests/test_config.py -q`.

**Likely files:** `services/cronjob-server/app/config.py`, `services/cronjob-server/app/storage/db.py`, `services/cronjob-server/requirements.txt`, `services/cronjob-server/tests/test_config.py`, `services/cronjob-server/.env.example`.

**Evidence:** Pending implementation.

### T25: Processor PostgreSQL test runner

- [ ] Complete T25.

**Module:** `data-pipeline`. **Dependencies:** T24. **Scope:** M (5 files).

**Acceptance:**

- Provide the same isolated real-PostgreSQL test contract as the source while keeping test utilities service-contained.
- No fallback to demo DB settings or silent skips; TEST_ARGS works and cleanup is limited to created resources.

**Verify:** From processor: `make test TEST_ARGS="tests/test_config.py -q"`; test rejection of non-test database configuration.

**Likely files:** `services/cronjob-server/scripts/test_db.py`, `services/cronjob-server/Makefile`, `services/cronjob-server/tests/conftest.py`, `services/cronjob-server/requirements-dev.txt`, `services/cronjob-server/README.md`.

**Evidence:** Pending implementation.

### T26: Processor schema migrations

- [ ] Complete T26.

**Module:** `data-pipeline`. **Dependencies:** T25. **Scope:** M (5 files).

**Acceptance:**

- Install phone-based access, raw/core constraints, migration history, and minimal applied-revision metadata in owned schemas.
- Migrations are rerunnable and preserve historical raw references/inactive identities; unrelated schemas are untouched.

**Verify:** From processor: `make test TEST_ARGS="tests/test_migrations.py -q"`; run migration twice against a test database with an unrelated sentinel table.

**Likely files:** `services/cronjob-server/app/cli.py`, `services/cronjob-server/app/storage/migrations.py`, `services/cronjob-server/app/migrations/001_access_raw_core.sql`, `services/cronjob-server/app/migrations/002_sync_state.sql`, `services/cronjob-server/tests/test_migrations.py`.

**Evidence:** Pending implementation.

#### Checkpoint after T26

- [ ] Processor config, isolated PostgreSQL harness, and migrations work together.
- [ ] Run processor `make ci`; no direct mock-schema dependency or alteration to unrelated tables.

### T27: Validated source client

- [ ] Complete T27.

**Module:** `data-pipeline`. **Dependencies:** T26, T18. **Scope:** M (5 files).

**Acceptance:**

- Fetch full snapshots/access through HTTP with bounded timeouts and concrete model validation.
- Reject unknown schema versions, incomplete counts, malformed ownership/references, and absent required resources before publication.

**Verify:** From processor: `make test TEST_ARGS="tests/test_source_client.py tests/test_snapshot_validation.py -q"`.

**Likely files:** `services/cronjob-server/app/source/client.py`, `services/cronjob-server/app/source/models.py`, `services/cronjob-server/app/pipeline/validate.py`, `services/cronjob-server/tests/test_source_client.py`, `services/cronjob-server/tests/test_snapshot_validation.py`.

**Evidence:** Pending implementation.

### T28: Shopee normalization

- [ ] Complete T28.

**Module:** `data-pipeline`. **Dependencies:** T27, T15. **Scope:** M (4 files).

**Acceptance:**

- Normalize Shopee orders/items and shared supplement entities with Decimal/null semantics and immutable source provenance.
- Keep full shop-qualified keys, Unix timestamps, native/unknown status mapping, and order enrichment references.

**Verify:** From processor: `make test TEST_ARGS="tests/test_shopee.py tests/test_common_mapping.py -q"`.

**Likely files:** `services/cronjob-server/app/connectors/common.py`, `services/cronjob-server/app/connectors/shopee.py`, `services/cronjob-server/tests/test_shopee.py`, `services/cronjob-server/tests/test_common_mapping.py`.

**Evidence:** Pending implementation.

### T29: Lazada and Shopify normalization

- [ ] Complete T29.

**Module:** `data-pipeline`. **Dependencies:** T28, T16, T17. **Scope:** M (4 files).

**Acceptance:**

- Normalize Lazada per-unit lines and mixed statuses without multiplying quantities.
- Normalize Shopify global IDs, line quantities, cancellation, and shipped status; preserve money and currency constraints.

**Verify:** From processor: `make test TEST_ARGS="tests/test_lazada.py tests/test_shopify.py -q"`.

**Likely files:** `services/cronjob-server/app/connectors/lazada.py`, `services/cronjob-server/app/connectors/shopify.py`, `services/cronjob-server/tests/test_lazada.py`, `services/cronjob-server/tests/test_shopify.py`.

**Evidence:** Pending implementation.

#### Checkpoint after T29

- [ ] All adapters consume the provider snapshot contract and preserve identity, money and status differences.
- [ ] Run processor `make ci`; cross-platform key collisions and malformed snapshots have explicit outcomes.

### T30: Atomic full-snapshot publication

- [ ] Complete T30.

**Module:** `data-pipeline`. **Dependencies:** T29. **Scope:** M (5 files).

**Acceptance:**

- Validate/stage the full dataset, then publish access/raw/core and applied marker in one transaction under the global lock.
- Recheck revision after acquiring the lock; unchanged replay is a no-op, stale revisions fail, and partial writes roll back.

**Verify:** From processor: `make test TEST_ARGS="tests/test_publication.py tests/test_replay.py -q"`; inject a late failing row and concurrent older/newer snapshots.

**Likely files:** `services/cronjob-server/app/pipeline/run.py`, `services/cronjob-server/app/storage/publish.py`, `services/cronjob-server/app/storage/sync_state.py`, `services/cronjob-server/tests/test_publication.py`, `services/cronjob-server/tests/test_replay.py`.

**Evidence:** Pending implementation.

### T31: Target deletion and raw history

- [ ] Complete T31.

**Module:** `data-pipeline`. **Dependencies:** T30, T19. **Scope:** M (5 files).

**Acceptance:**

- Apply only explicit tombstones in dependency order; retain observed immutable raw versions and inactive access identities.
- Missing live keys without tombstones fail the entire run; replayed markers are harmless and history is not overwritten.

**Verify:** From processor: `make test TEST_ARGS="tests/test_reconciliation.py tests/test_raw_history.py -q"`.

**Likely files:** `services/cronjob-server/app/pipeline/reconcile.py`, `services/cronjob-server/app/storage/publish.py`, `services/cronjob-server/app/storage/raw.py`, `services/cronjob-server/tests/test_reconciliation.py`, `services/cronjob-server/tests/test_raw_history.py`.

**Evidence:** Pending implementation.

#### Checkpoint after T31

- [ ] Atomic publication, unchanged replay, raw retention and tombstones work in real PostgreSQL.
- [ ] Run publication/replay/reconciliation/history tests; a forced failure leaves the prior dataset intact.

### T32: Frozen-clock mart views

- [ ] Complete T32.

**Module:** `data-pipeline`. **Dependencies:** T31. **Scope:** M (4 files).

**Acceptance:**

- Install settings and all eight existing mart views with unchanged formulas/thresholds.
- Test single refund subtraction, nullable financial completeness, no fanout, local date windows, and fixed business time.

**Verify:** From processor: `make test TEST_ARGS="tests/test_mart_economics.py tests/test_mart_operations.py tests/test_mart_clock.py -q"`.

**Likely files:** `services/cronjob-server/app/migrations/003_marts.sql`, `services/cronjob-server/tests/test_mart_economics.py`, `services/cronjob-server/tests/test_mart_operations.py`, `services/cronjob-server/tests/test_mart_clock.py`.

**Evidence:** Pending implementation.

### T33: Full-scenario regression coverage

- [ ] Complete T33.

**Module:** `data-pipeline`. **Dependencies:** T32. **Scope:** M (4 files).

**Acceptance:**

- Adapt service-contained full snapshot inputs with phone IDs while preserving original business data.
- Actual normalization/publication/views produce 1,344 orders and 29 candidates (10/10/9), with zero for the healthy Shopee control.

**Verify:** From processor: `make test TEST_ARGS="tests/test_full_scenarios.py -q"`; trace fixture provenance and ensure the MVP default seed is unchanged.

**Likely files:** `services/cronjob-server/tests/fixtures/full_snapshot.json`, `services/cronjob-server/tests/fixtures/full_expected.json`, `services/cronjob-server/tests/test_full_scenarios.py`, `services/cronjob-server/tests/fixtures/README.md`.

**Evidence:** Pending implementation.

#### Checkpoint after T33

- [ ] Pipeline meets all table/view and small/large dataset acceptance targets.
- [ ] Run processor `make ci`; verify 1,344 orders, 29 candidates and the healthy control in the separate regression fixture.

### T34: Durable run records

- [ ] Complete T34.

**Module:** `sync-control`. **Dependencies:** T33. **Scope:** M (4 files).

**Acceptance:**

- Persist the specified run states, trigger, requester, minimum/applied revision, counts and bounded errors.
- Atomic enqueue/claim and operation identity survive restart; no unpersisted acceptance or phone/payload error leakage.

**Verify:** From processor: `make test TEST_ARGS="tests/test_runs.py -q"`; cover duplicate enqueue intent and restart/claim races.

**Likely files:** `services/cronjob-server/app/migrations/004_runs.sql`, `services/cronjob-server/app/storage/runs.py`, `services/cronjob-server/app/jobs/models.py`, `services/cronjob-server/tests/test_runs.py`.

**Evidence:** Pending implementation.

### T35: Manual trigger and worker

- [ ] Complete T35.

**Module:** `sync-control`. **Dependencies:** T34. **Scope:** M (5 files).

**Acceptance:**

- POST sync-runs validates current caller, accepts only an empty object and returns a persisted stable run ID; status/list routes scope ownership.
- One worker invokes the pipeline, honors minimum revision, and marks already-applied work as successful no-op.

**Verify:** From processor: `make test TEST_ARGS="tests/test_manual_sync.py tests/test_worker.py -q"`; manual runs work with interval disabled.

**Likely files:** `services/cronjob-server/app/api/runs.py`, `services/cronjob-server/app/jobs/worker.py`, `services/cronjob-server/app/main.py`, `services/cronjob-server/tests/test_manual_sync.py`, `services/cronjob-server/tests/test_worker.py`.

**Evidence:** Pending implementation.

#### Checkpoint after T35

- [ ] Manual full sync and persisted status work with scheduling disabled.
- [ ] Run processor `make ci`; stable run IDs, scoped status and revision-gated no-op behavior are tested.

### T36: MCP-facing mutation facade

- [ ] Complete T36.

**Module:** `sync-control`. **Dependencies:** T35, T20. **Scope:** M (5 files).

**Acceptance:**

- Forward typed CRUD for all business/admin entities through HTTP; retain caller scope and source idempotency key.
- Persist intent before sending; confirmed writes return source result plus queued run, uncertain writes return pending status without claiming failure.

**Verify:** From processor: `make test TEST_ARGS="tests/test_mock_facade.py -q"`; exercise every resource/method and source reference/conflict errors.

**Likely files:** `services/cronjob-server/app/api/mock.py`, `services/cronjob-server/app/storage/intents.py`, `services/cronjob-server/app/migrations/005_intents.sql`, `services/cronjob-server/app/main.py`, `services/cronjob-server/tests/test_mock_facade.py`.

**Evidence:** Pending implementation.

### T37: Recovery and bounded retries

- [ ] Complete T37.

**Module:** `sync-control`. **Dependencies:** T36. **Scope:** M (5 files).

**Acceptance:**

- Recover pending mutations and interrupted runs using the original key/commit marker; source commits are not duplicated.
- Use at most three transient attempts with 1/2-second backoff; unknown outcomes remain explicit and validation errors do not retry.

**Verify:** From processor: `make test TEST_ARGS="tests/test_recovery.py tests/test_retries.py -q"`; inject crashes before source send, after source commit, and after target commit.

**Likely files:** `services/cronjob-server/app/jobs/recovery.py`, `services/cronjob-server/app/jobs/worker.py`, `services/cronjob-server/app/storage/intents.py`, `services/cronjob-server/tests/test_recovery.py`, `services/cronjob-server/tests/test_retries.py`.

**Evidence:** Pending implementation.

#### Checkpoint after T37

- [ ] Mutation forwarding closes the source-success/processor-crash gap.
- [ ] Run facade/recovery/retry suites; do not claim unknown writes failed or completed without evidence.

### T38: Scoped core and raw reads

- [ ] Complete T38.

**Module:** `sync-control`. **Dependencies:** T37. **Scope:** M (5 files).

**Acceptance:**

- Expose all core entity lists/key lookups, raw evidence, and allowed shops with revision metadata and concrete schemas.
- Intersect current source grants with target ownership; encode composite keys, restrict filters, paginate consistently, and fail closed on source outage.

**Verify:** From processor: `make test TEST_ARGS="tests/test_processed_reads.py -q"`; include shared/unrelated users and membership deletion before sync.

**Likely files:** `services/cronjob-server/app/api/reads.py`, `services/cronjob-server/app/storage/reads.py`, `services/cronjob-server/app/source/access.py`, `services/cronjob-server/app/main.py`, `services/cronjob-server/tests/test_processed_reads.py`.

**Evidence:** Pending implementation.

### T39: Mart reads and settings

- [ ] Complete T39.

**Module:** `sync-control`. **Dependencies:** T38, T32. **Scope:** M (5 files).

**Acceptance:**

- Expose all eight views with scoped rows and allowed filters; reject arbitrary relation/column expressions.
- Admin settings GET/PATCH validates fixed as_of and positive windows, honors idempotency, and requires no source sync.

**Verify:** From processor: `make test TEST_ARGS="tests/test_mart_api.py -q"`; verify changes recompute results without advancing time automatically.

**Likely files:** `services/cronjob-server/app/api/marts.py`, `services/cronjob-server/app/storage/marts.py`, `services/cronjob-server/app/api/settings.py`, `services/cronjob-server/app/main.py`, `services/cronjob-server/tests/test_mart_api.py`.

**Evidence:** Pending implementation.

#### Checkpoint after T39

- [ ] Processed core/raw/mart access is scoped by current grants, and settings updates are explicit.
- [ ] Run processor `make ci`; revocation-before-sync, source outage, and global-count leakage checks pass.

### T40: Seconds-based scheduling

- [ ] Complete T40.

**Module:** `sync-control`. **Dependencies:** T39. **Scope:** M (4 files).

**Acceptance:**

- Interval 0 disables periodic work; positive N schedules after recovery/startup and N seconds after the queue drains.
- Manual/mutation arrivals wake the worker; long jobs do not overlap or accumulate missed ticks; business clock is unchanged.

**Verify:** From processor: `make test TEST_ARGS="tests/test_scheduler.py -q"`; use an injected clock, restart cases and a job longer than its interval.

**Likely files:** `services/cronjob-server/app/jobs/scheduler.py`, `services/cronjob-server/app/jobs/worker.py`, `services/cronjob-server/app/main.py`, `services/cronjob-server/tests/test_scheduler.py`.

**Evidence:** Pending implementation.

### T41: Dependency health and safe diagnostics

- [ ] Complete T41.

**Module:** `sync-control`. **Dependencies:** T40. **Scope:** M (5 files).

**Acceptance:**

- Readiness checks migrations/database/worker while liveness remains independent of temporary source failures.
- Errors/logs expose run stage and safe counts/codes without phone IDs, request bodies, payloads or credentials.

**Verify:** From processor: `make test TEST_ARGS="tests/test_health.py tests/test_diagnostics.py -q"`; simulate database/source loss and stopped worker.

**Likely files:** `services/cronjob-server/app/api/health.py`, `services/cronjob-server/app/main.py`, `services/cronjob-server/app/jobs/worker.py`, `services/cronjob-server/tests/test_health.py`, `services/cronjob-server/tests/test_diagnostics.py`.

**Evidence:** Pending implementation.

#### Checkpoint after T41

- [ ] Interval, startup recovery, readiness and diagnostics complete the control module.
- [ ] Run processor `make ci`; fake-clock tests prove no overlaps/backlog and no change to frozen business time.

### T42: Two-service CRUD integration harness

- [ ] Complete T42.

**Module:** `integration`. **Dependencies:** T41, T20. **Scope:** M (5 files).

**Acceptance:**

- Build/start separate service containers with a dedicated test PostgreSQL instance; migrate/seed explicitly and use actual HTTP only.
- Exercise all source/admin entities through the facade, verify run IDs/revisions, 20 orders per user, shared visibility, deletions, and all eight mart reads.

**Verify:** From root: `python scripts/test-mock-pipeline.py --suite crud`; verify cleanup touches only resources created by that run.

**Likely files:** `scripts/test-mock-pipeline.py`, `services/cronjob-server/tests/e2e/compose.yml`, `services/cronjob-server/tests/e2e/test_crud.py`, `services/cronjob-server/tests/e2e/conftest.py`, `services/cronjob-server/tests/e2e/requirements.txt`.

**Evidence:** Pending implementation.

### T43: Two-service failure scenarios

- [ ] Complete T43.

**Module:** `integration`. **Dependencies:** T42. **Scope:** M (3 files).

**Acceptance:**

- Prove restart recovery, unchanged replay, failed-snapshot rollback, source outages, and edits arriving during a sync across separate processes.
- Prove tenant-scoped reads/counts/errors and immediate membership removal; retained raw evidence does not bypass current access.

**Verify:** From root: `python scripts/test-mock-pipeline.py --suite recovery`.

**Likely files:** `services/cronjob-server/tests/e2e/test_recovery.py`, `services/cronjob-server/tests/e2e/test_access.py`, `scripts/test-mock-pipeline.py`.

**Evidence:** Pending implementation.

### T44: Cross-service CI coverage

- [ ] Complete T44.

**Module:** `integration`. **Dependencies:** T43. **Scope:** M (3 files).

**Acceptance:**

- Add the proposed read-only, secret-free PR workflow with path filters covering both services, harness/Compose files, and itself.
- Run the full pair suite; retain the existing reusable service CI and avoid any deploy/permission expansion.

**Verify:** From root: `python scripts/test-mock-pipeline.py --suite all`; validate workflow syntax and path-filter cases; inspect the first eligible PR check when available.

**Likely files:** `.github/workflows/mock-pipeline-e2e.yml`, `scripts/test-mock-pipeline.py`, `services/cronjob-server/tests/e2e/compose.yml`.

**Evidence:** Pending implementation.

#### Checkpoint after T44

- [ ] Separate service processes pass normal and failure integration flows; both service paths trigger the proposed CI check.
- [ ] Run the full pair harness and validate workflow permissions/path filters; record any remote CI evidence still unavailable.

### T45: Source container and usage handoff

- [ ] Complete T45.

**Module:** `mock-source`. **Dependencies:** T44. **Scope:** M (5 files).

**Acceptance:**

- Document migrate/seed/CRUD/snapshot commands and every env var with placeholders; document deletion/phone/shared-user behavior.
- Service-only image includes fixtures/migrations and runs as non-root; restart and repeated seeding do not reset edited data.

**Verify:** From source: `make ci` and `docker build -t mock-data-server .`; use the pair harness to exercise migration/seed from the image.

**Likely files:** `services/mock-data-server/README.md`, `services/mock-data-server/AGENTS.md`, `services/mock-data-server/.env.example`, `services/mock-data-server/Dockerfile`, `services/mock-data-server/tests/test_image_assets.py`.

**Evidence:** Pending implementation.

### T46: Processor container and MCP handoff

- [ ] Complete T46.

**Module:** `sync-control`. **Dependencies:** T45. **Scope:** M (5 files).

**Acceptance:**

- Document encoded composite-key CRUD, run polling, pending/unknown outcomes, interval semantics, scoped reads and admin boundary.
- Document one-worker deployment, frozen-clock limitations and internal upstream URL; image packages migrations without repository-root runtime files.

**Verify:** From processor: `make ci` and `docker build -t cronjob-server .`; run documented examples against the isolated pair.

**Likely files:** `services/cronjob-server/README.md`, `services/cronjob-server/AGENTS.md`, `services/cronjob-server/.env.example`, `services/cronjob-server/Dockerfile`, `services/cronjob-server/tests/test_image_assets.py`.

**Evidence:** Pending implementation.

### T47: Acceptance evidence and final review

- [ ] Complete T47.

**Module:** `integration`. **Dependencies:** T46. **Scope:** S (2 files).

**Acceptance:**

- Record successful source/processor CI, image builds, full pair suite, exact MVP/full-regression counts, and every approved spec's acceptance mapping.
- Review runtime boundaries, input validation, secrets, migrations, and error paths; leave unmet checks open and report actual deployment prerequisites.

**Verify:** Use the successful task 45/46 CI/build results and run `python scripts/test-mock-pipeline.py --suite all` after final changes; repeat only checks invalidated by subsequent edits.

**Likely files:** `tasks/todo.md`, `tasks/plan.md`.

**Evidence:** Pending implementation.

#### Checkpoint after T47

- [ ] Every task and approved spec acceptance item has passing evidence, or remains explicitly unchecked.
- [ ] Record the review outcome and deployment inputs; do not merge/deploy as part of this plan.
