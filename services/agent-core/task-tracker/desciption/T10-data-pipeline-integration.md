# T10 Agent Core to Commerce Data Pipeline Integration Plan

> **For agentic workers:** Use `superpowers:executing-plans` for inline implementation, or `superpowers:subagent-driven-development` when explicitly selected. Track steps with checkboxes. This task record does not start implementation or authorize paid calls/deployment.

**Goal:** Make the existing chat/report flow read synchronized commerce data through Shop Data MCP instead of Core's business fixtures.

**Architecture:** `shopops-chat → shopops-chat-api → agent-core → shop-data-mcp → derived PostgreSQL`. The source/processor remain `mock-data-server → cronjob-server`. Core translates its allowlisted tools into read-only MCP queries; no model or sandbox receives database credentials or private service access.

**Tech Stack:** Existing Python/FastAPI, Core's MCP HTTP client, the Data MCP SDK service, PostgreSQL pipeline, pytest and existing React chat. Preserve service-private environments, pinned dependencies and shared CI delivery.

**Spec:** [Integration design](#integration-design), [Core MCP contract](../../contracts/mcp-integration.md), [managed runtime](../../agents_api_managed_runtime_spec.md), [T09](T09-chat-client-integration.md), [tracker](../task_list.md#commerce-data-integration-follow-up-t10).

**Status:** Ready for integration (offline implementation; hosted acceptance remains UNVERIFIED). **Difficulty:** D5 — Very hard. Identity translation, mismatched analytical grains, snapshot/freshness semantics, restricted query roles and real multi-service verification cross service boundaries.

## Starting points and dependencies

- Task planning base: committed T09 handoff/review `d3f2602`; its two P1 findings remain open in the recorded review. Do not consume another owner's uncommitted fixes.
- Pipeline is merged into `develop` at `5262ba4` (PR #6). Data MCP is published on `codex/shop-data-mcp-design`, inspected at `e663f88`, and is not merged into that baseline.
- Read the pinned Data MCP [README](https://github.com/swe-squad/shopops2026/blob/e663f88/services/shop-data-mcp/README.md), [integration contract](https://github.com/swe-squad/shopops2026/blob/e663f88/services/shop-data-mcp/INTEGRATION.md), [catalog](https://github.com/swe-squad/shopops2026/blob/e663f88/services/shop-data-mcp/catalog.example.json) and [handoff](https://github.com/swe-squad/shopops2026/blob/e663f88/services/shop-data-mcp/HANDOFF.md). Pipeline [source](https://github.com/swe-squad/shopops2026/blob/5262ba4/services/mock-data-server/README.md) and [processor](https://github.com/swe-squad/shopops2026/blob/5262ba4/services/cronjob-server/README.md) are authoritative for seeded records and synchronization.
- The integration lead selects/records an approved committed implementation base containing the pipeline, Data MCP and required T09 fixes. Contract/unit tests can be prepared before that integration; end-to-end acceptance cannot.
- Full chat acceptance requires fixes for T09-R01/R02. Paid hosted proof additionally requires accepted T08 boundary-probe/child-role evidence and explicit operator opt-in. These gates do not prevent offline contract work.
- Branch `feat/agent-core-data-mcp`; native worktree label `agent-core-data-mcp`; fallback `/tmp/shopops2026-agent-core/T10`. No implementation workspace is created by this task update.

## Scope and ownership

Read root and affected service AGENTS.md files. T10 owns only the following follow-up scope; previous task ownership and other agents' work remain intact.

| Area | Responsibility / proposed paths |
| --- | --- |
| Core | Create `services/agent-core/app/tools/shop_data.py`, `config/shop-data-bindings.example.json`, `contracts/shop-data-integration.md`, adapter/protocol tests under `tests/tools/` and service-local integration support. Update `app/tools/bridge.py`, `client.py`, `validation.py`, `app/composition.py`, config/contracts and profile-specific instructions only as needed for this approved profile |
| Data MCP | Add an isolated approved projection migration, catalog entries, least-privilege provisioning and tests under `services/shop-data-mcp/`; coordinate with its owner and import committed amendments |
| Demo identity alignment | Change only the single demo phone fixture, related tests and documentation in `services/shopops-chat-api/`; adjust chat phone examples/tests where necessary. Keep the Core owner, one-shop UI and conversation APIs intact |
| Evidence/docs | This tracker/description, affected service `.env.example`/READMEs and ignored service-local test evidence |

No direct Core database connection to pipeline tables, sibling runtime imports, unrestricted SQL/model tools, raw approval bypass, CRUD/refresh capabilities, data reset, new vault, production phone authentication, UI redesign or root workflow/harness changes. Use service-local test support; existing root harnesses may be run unchanged.

## Integration design

### One user and one shop

Use the source's synthetic demo phone `+84900000001` and exactly one selected source shop, `shopee-open-platform:1001`. Align the chat's single positive phone fixture from its earlier `+15550000001` sample in an isolated amendment; preserve its internal `tenant-a` / `alice`, Core credential `local-alice`, and Core shop `shop-a`. There is still one supported demo login, no OTP and no new Core permission grant. Keep negative identity fixtures unchanged.

Create a trusted versioned binding:
`(tenant-a, alice, shop-a) → (+84900000001, shopee-open-platform:1001)`.
The model/browser cannot choose or override this binding, phone, shop key, endpoint or credentials. Keep phone identity out of prompts, ToolResults, artifacts and logs. Every Data MCP request carries the server-resolved `X-Phone-Number`; every data tool call supplies the explicitly selected `shop_key`, even if source membership grants other shops.

Pin a binding reference (ID/version/digest) in the new data-enabled conversation configuration. Keep legacy snapshots compatible. A binding change requires a new administrative revision, not silently retargeting an existing conversation. Core still checks tenant/user/shop/conversation ownership and run grants before any upstream call; Data MCP independently rechecks authoritative phone membership and uses the restricted per-shop query login. No shared privileged PostgreSQL login is acceptable.

### Protocol and credentials

Add an explicitly approved remote profile, proposed `shop-data-read-v1`, with a new immutable hosted registry revision, proposed `returns-hosted-data-v1`. Existing `mock-v1` profiles, HMAC-authenticated knowledge/history and old pinned conversations remain usable. The new profile cannot fall back to fixtures, `none` or a different dataset when unavailable.

The Data MCP endpoint is `/mcp`; it uses `X-Phone-Number`, not Core's scoped HMAC bearer protocol. Implement an internal profile-specific header policy while retaining existing URL allowlisting, DNS/redirect protections, bounded JSON/SSE parsing, session cleanup and total tool budget. Test initialize, notification, call and cleanup against the actual SDK server. Do not globally remove Core credential checks or forward a browser token to the MCP server.

Use `SHOP_DATA_MCP_URL` in Core's `.env.example`/README with a localhost value. Runtime CapRover configuration uses `http://srv-captain--<data-mcp-app>:8000/mcp`, never a public service URL or hardcoded dev default. Registry snapshots and binding versions remain authoritative for conversations; environment values do not rewrite old snapshots. Data MCP requires its own mounted config/catalog, CA and restricted DSNs; they never enter Core, chat or the OpenAI environment. Startup/profile activation fails closed for missing/mismatched binding/config.

The agent retains only its four public Core tools. Translate `get_return_metrics` and `get_review_summary` to approved Data MCP read operations; keep `search_knowledge` and `get_conversation_history` on existing paths. Never grant arbitrary SQL, raw queries, all discovered MCP tools or the new cronjob CRUD tools to the model. Query templates use fixed catalog IDs and validated parameters; reject unsupported SKU syntax before constructing SQL.

### Data contract and analytical grain

The current catalog's `shop_window_metrics` is shop/period grain with configured recent/baseline windows. Its rates are fractions. It cannot directly fulfill Core's arbitrary SKU/date requests, equal-length preceding baseline or percentage units. `product_review_metrics` also exposes only configured periods and intentionally excludes review bodies. Add approved sanitized projections before claiming compatibility; do not rename fields or multiply a rate and assume the remaining semantics match.

Freeze the following logical datasets in `contracts/shop-data-integration.md` with the Data MCP owner before implementing translation:

- `agent_snapshot_v1`: selected shop's published `source_revision`, successful publication timestamp and `analysis_as_of`, sourced from the processor's synchronized state/settings/successful run. Missing publication is unavailable, not an empty business result.
- `agent_sku_catalog_v1`: known SKU identifiers for the selected shop, allowing unknown SKU to be distinguished from a known SKU with zero eligible orders.
- `agent_order_cohorts_v1`: one distinct shop/SKU/order with local business date and a return-request flag; no buyer contacts or raw payloads. Duplicate order lines/return records must not multiply counts.
- `agent_review_facts_v1`: approved SKU/date, stable review/source identifiers and precomputed category flags. Review bodies/customer data are not exposed. These projections must preserve the per-shop role/view boundary and require only `data:read`, not raw approval.

Planning metric definition for the new profile: `orders` counts distinct fulfilled (`shipped|completed`) orders containing the SKU, by order timestamp in the requested inclusive Asia/Ho_Chi_Minh dates. `returns` counts the subset with an observed order-level return request before the pipeline cutoff. This is an order-cohort/request metric, not proof that the requested SKU itself was returned or that a return completed. Publish that caveat in profile/tool instructions and the dataset contract. Do not silently reuse another denominator or raw status convention.

Compute the immediately preceding interval with the same inclusive day count. Convert local `[start_date, end_date]` into the correct half-open timestamps. Preserve Core's six-decimal percentage rates, percentage-point change and null rates when the denominator is zero. Do not infer zero from missing/unseeded data, denied access or truncated results. Reject incomplete/future coverage beyond `analysis_as_of` instead of silently clipping the requested range.

Review categories are `negative_rating` (rating ≤2) and `sizing_mentions` (negative rating plus the pipeline's documented sizing rule). Categories may overlap. Counts must cover the full requested interval; each evidence list is a documented deterministic sample of at most 20 safe source references, never raw review text. Freeze source-ID and category semantics in the shared contract and test them independently.

Numbers and publication metadata must refer to the same database snapshot. Aggregate in one coherent query or verify equal source revision/as-of markers across bounded queries; reject mixed snapshots. Pipeline `as_of` is a frozen analysis clock. Data MCP `queried_at` proves read time, not ingestion completeness or freshness. Carry actual publication metadata/provenance and never describe a refresh as historical interval coverage. No model-triggered refresh is added here.

### Core results, provenance and failure handling

Data MCP returns columns/preview/result handles, not Core ToolResult envelopes. Validate schemas, ownership, known columns, numeric types, pagination, expiry and truncation before constructing `schema_version=1` results. Use `read_result` only for a verified result in the same phone/shop; cap work inside the existing 15-second total tool budget. `truncated`/`input_truncated`, malformed rows, changed membership and missing provenance fail without partial metrics or fixture fallback.

Preserve existing Core argument/result/context validation and the 32 KiB ToolResult limit. Source references must identify the actual dataset/query result and published revision; never manufacture `fixture:` references for remote data or expose a phone, DSN, private URL or raw payload. Keep knowledge references separate. Existing root validation must accept only successful persisted source pairs from that session/turn.

Keep the shipped approved runtime bundle immutable. Reuse the helper/report schema when compatible; any changed skill/helper bytes require a new bundle version/digest and reviewed registry revision. Follow-up uses the pinned conversation/session. Data-profile cutover requires an explicit new conversation/revision after pending work is reconciled; preserve old history and record cleanup of obsolete test resources.

## Review focus

- A forged phone/shop, changed membership or permissive database role must not disclose another shop's rows/results.
- SKU/date/grain/percentage mismatches, duplicate lines and empty denominators must not yield believable but incorrect reports.
- Truncated preview, incomplete publication or a revision change between queries must not be reported as complete/fresh data.
- Failed remote reads must not use old fixture numbers or silently change identity/profile.
- Enabling the integration must not grant CRUD/raw/refresh tools or leak DSNs/phone headers into model content or logs.

## Implementation steps

- [x] **1. Publish the frozen integration contract.** Record exact dependency SHAs, selected identity/shop binding, projection schemas/roles, metric/cutoff definitions, query/provenance envelope and error mapping in `contracts/shop-data-integration.md`. Add failing contract tests for unsupported catalog grain/auth before coding the adapter.
- [x] **2. Add approved Data MCP projections.** Coordinate an additive migration/catalog/provisioning commit with the MCP owner. Test known/unknown SKU, zero counts, duplicate lines/returns, boundary timestamps, safe review categories, missing publication and cross-shop database denial using disposable PostgreSQL. Do not alter pipeline source/writer permissions or expose raw bodies.
- [x] **3. Implement the Core profile/adapter.** Add trusted binding validation, profile-specific transport headers and fixed data-tool translation. Reproduce malformed/truncated/expired/denied/mixed-revision cases RED, then implement GREEN. Retain legacy mock, knowledge/history, source validation, deadlines and no-extra-tool regressions.
- [x] **4. Align the one demo phone and configuration.** Update only the single chat fixture and related examples/tests to the seeded phone; keep the same owner/Core shop. Publish the data-enabled registry revision and binding example; document manual source seed, initial sync, restricted roles/CA/config and deliberate new-conversation activation. Coordinate with the accepted T09 fix handoff; never edit its active worktree.
- [x] **5. Run real multi-service offline acceptance.** Add a service-local harness under `services/agent-core/` that creates isolated source/derived/control databases, seeds/syncs, starts real Data MCP and Core HTTP services plus the chat adapter, and uses a fake model provider. Exercise phone login, metrics/reviews, report download, follow-up, restart and scope rejection. Compare exact results to an independent seeded-data oracle. Apply a test-only source mutation and synchronize it; the next appropriate query must reflect the new source revision/counts, proving it does not use Core fixtures. Never point tests at the demo/operational DB.
- [x] **6. Verify, review and hand off.** Run affected services' `make ci`, focused adapter/protocol tests, disposable PostgreSQL projection/isolation tests and the explicit cross-service harness. Run existing pipeline/MCP harnesses unchanged. Record Docker packaging, dependency commits, migrations/role setup, browser API evidence and cleanup of every test process/container/database. Mark Ready for integration after those checks; do not mark Done from mocked transport tests.
- [ ] **7. Run gated hosted acceptance only when eligible.** After T08/T09 prerequisites and explicit paid opt-in, repeat the data-backed report/follow-up path through the actual chat/Core APIs with synthetic pipeline data. Reuse approved skills/child proof, compare numeric values to this pipeline's oracle (not the older fixed 5%/15% fixture), and record aggregate provenance/isolation/cleanup. Missing credentials, unavailable services or unaccepted proof remain UNVERIFIED.

## Verification and handoff

Default CI has no external network/provider calls. Keep `AGENT_CORE_LIVE` and `AGENT_CORE_LIVE_HOSTED` unset; use separate explicit offline flags for disposable PostgreSQL/cross-service checks. Each service keeps its own environment/process: never import a sibling runtime module or share its SQLite DB. Tests may coordinate owned processes through HTTP.

A complete handoff records branch/worktree/base and dependency SHAs, changed service paths, projection/catalog/binding versions, RED→GREEN and full CI results, database-role/isolation checks, pipeline-to-answer mutation proof, restart/report/follow-up results and resource cleanup. Read-only demo data is synthetic, even when stored in real PostgreSQL; it is not live commerce-platform ingestion.

## Implementation handoff

**Implementation:** complete for offline integration. **Status:** Ready for integration.
**Hosted end-to-end:** UNVERIFIED; do not mark Done or claim deployed/live acceptance.

- Worktree: `/tmp/shopops2026-agent-core/T10`.
- Branch: `feat/agent-core-data-mcp`; combined dependency base `09a30a1`.
- Inputs: planning `15202f5`, pipeline `5262ba4`, Data MCP `e663f88`,
  accepted T09 fixes `311aa4e` / `e34056f`. Preparatory checkpoint `f6dbff9`.
- Changed services: `agent-core`, `shop-data-mcp`, `shopops-chat-api`, `shopops-chat`.
  Upstream dependency merges precede the implementation base; no new root workflow,
  source/processor runtime change, production reset or deployment is part of T10.

### Delivered behavior

- Immutable binding reference (ID/version/digest) in conversation config; private
  trusted binding file with owner/shop/phone and verified demo coverage start.
- Opt-in `shop-data-read-v1` / `returns-hosted-data-v1`; legacy snapshots and hosted
  bundle bytes/digest unchanged. Header policy remains profile-specific, retaining
  DNS allowlisting, bounded parsing, cleanup and total 15-second bridge deadline.
- Fixed metrics/review queries over four approved projections, complete counts,
  bounded safe review samples, publication/clock consistency including empty samples,
  exact provenance/column/type/expiry checks, no fixture fallback or extra model tools.
- Additive derived projections `004-agent-projections.sql`, isolated agent catalog,
  and authoritative source membership view `005-source-membership.sql`. Apply **005
  in source before 003**; apply 004 in derived after 002. No writer-role changes.
- Single positive demo phone aligned to `+84900000001`; negative identity fixtures
  and Core owner/shop/credential remain intact.

### Decisions and review fixes

- Operator explicitly chose a configured independently verified demo coverage bound.
  The binding pins `2026-10-17`; the harness compares every selected-shop seeded SKU,
  cohort and review fact against an independent complete source-fixture oracle and
  records its digest. This does not claim arbitrary real-platform history coverage.
- Preserved old registry endpoint revisions when a new endpoint is activated; a
  regression test reproduces and fixes startup rejection of mixed pinned endpoints.
- Actual SDK denial is text, not a Core JSON error envelope. MCP now emits a stable
  `permission_denied` marker; only the phone-profile parser maps it. SDK and client
  regression tests prove this, with legacy parsing unchanged.
- RED→GREEN: missing catalog gate/binding/adapter, incomplete coverage, empty-sample
  mixed-publication detection, impossible category counts, endpoint revisions and
  SDK authorization marker. No blocker was dismissed as a style issue.

### Verification evidence

- Core final `make ci`: **466 passed, 2 skipped**, using Python 3.14 explicitly
  (host `python3` defaults to 3.13).
- Data MCP PostgreSQL suite: **246 passed, 1 skipped** before the final error-marker
  amendment; final `make ci`: **219 passed, 29 skipped** without a database; actual
  SDK marker suite **7 passed** and final multi-service harness cover that amendment.
- Unchanged root pipeline/MCP harness: **1 passed**. Its `.resolve()` loses venv
  context; a temporary interpreter wrapper was used without changing the harness.
- Chat API final `make ci`: **104 passed, 4 skipped**, lint passes; one pre-existing
  Starlette/httpx deprecation warning. Frontend final `make ci`: **48 passed**, lint/build
  pass. Docker images for all four affected services build; packaged Python syntax
  and frontend runtime nginx checks pass. Core/MCP rebuilt after final transport fix.
- Graphify AST updates run for all four changed services; SQL extractor availability
  limits graph coverage and is not counted as SQL validation.

Run the real offline acceptance from `services/agent-core`:

```sh
.venv/bin/python scripts/t10_acceptance.py \
  --pipeline-python /tmp/t10-pipeline-venv/bin/python \
  --chat-python ../shopops-chat-api/.venv/bin/python
```

The pipeline interpreter must have that service's pinned dependencies installed.
The harness launches separate service processes over loopback, disposable source,
derived and control databases, actual MCP SDK/HTTP, Core and chat HTTP, and a test-only
fake provider. Source seed oracle: **3 SKUs, 5 cohorts, 5 reviews**; canonical fixture
SHA-256 `4da5766b42d34b5e086720992a4227ada03297d8e00bc7372058c03acb41e166`.
It checks phone login, metrics/reviews/knowledge, report download/hash, follow-up,
chat+Core restarts, scope/result/artifact denials, and a source mutation followed by
sync (**returns 0→1**, **revision 1→2**). Core/chat receive no database credentials.
Final exact-version harness exited 0 with `passed=true` and `cleanup=true`; also
verified direct MCP HTTP cross-shop query/result rejection, same-shop-other-user
artifact denial, and live selected-shop revocation while another shop remains
authorized. Ignored local evidence: `.evidence/t10/acceptance-final.json`.

This is browser-facing API evidence plus frontend tests/build, not a manual browser
screenshot or actual hosted specialist proof.

Every harness run cleans its child processes, Docker container and volumes in finally;
validation images and temporary interpreter wrappers were removed. Service-private
installed dependencies remain reusable. No operational DB, secret file, deployed
service or paid provider call was used.

### Remaining separately gated evidence

Step 7 remains unchecked: accepted T08 hosted boundary/child-role proof is still
missing in the committed task record, and T10 paid hosted opt-in has not been given.
The implementation and offline acceptance do not establish those claims. Run hosted
acceptance only after those prerequisites, with the pipeline oracle and cleanup.

Environment note: sandboxed DNS/TestClient attempts stalled or timed out (including
`test_phone_header_all_requests_no_bearer_and_session_cleanup`); the same tests and
full CI passed outside the sandbox with only offline/loopback access. No such failed
attempt is counted as a pass. Final process scan found no pytest/uvicorn leftovers.
