# Product workspace delivery — 2026-10-31

Status: complete for implementation and deployment preparation.

Branch `codex/shopops-web-client` integrates develop `082006d`, including merged PRs #12 and #14. No feature commit, push, PR, deployment or live configuration inspection was performed.

## Delivered

- Shopee-inspired Products gallery, shop/SKU search, product details and review/order/return evidence. Optional images use safe HTTPS loading or an honest placeholder. Observed sale prices and order-associated returns keep their actual meaning.
- Active visible views poll every two seconds; same-scope stale evidence remains marked after transient failures, while permission/selection failures clear it. Explicit product deep links survive unlock, navigation and browser history.
- Catalog reads use the private HTTP route `shopops-web → shopops-api → cronjob-server → mock-data-server → PostgreSQL`. Browser credentials do not select source identity. Complete paginated reads require coherent revisions and current access; cache hits avoid rereading unchanged history without bypassing grants.
- New opt-in `returns-hosted-v2` agent registration and immutable runtime bundle `1.1.0` teach scoped mart-first investigation, permitted raw evidence and capability-gated refresh/reconciliation. Existing reports, immutable bundle `1.0.0` and default registrations remain compatible.
- Production API image defaults to source mode and requires its runtime URL/identity. Aggregate-only `python -m app.catalog_check` tests the configured HTTP route and fails empty/unavailable/incoherent data. Deployment docs specify `POSTGRES_PORT=15432` on both existing data services without changing their generic defaults or resetting records.
- Preserved the separately developed chat bridge and in-memory Connections demo. Products does not depend on demo connection flags.

## Verification

| Check | Result |
| --- | --- |
| shopops-api `make ci` | 109 passed; Ruff passed. All 109 also passed on Python 3.14. |
| shopops-web tests/lint/build | 68 passed; lint and build passed. |
| agent-core `make ci` on integrated develop | 487 passed, 2 live suites skipped; Ruff passed. |
| Full workspace browser suite on integrated develop | 21 passed, including catalog polling, denied selections, chat navigation, Connections persistence, direct product URLs and responsive viewports. |
| Offline runtime configuration | Both data services accept explicit PostgreSQL port 15432. No DB connection attempted. |
| Render review | Product gallery/detail inspected; phone/tablet/desktop and landscape checked; placeholder contrast corrected. |
| Independent review and simplification | Earlier stale-access and polling-fanout findings fixed and reverified. Final deployment/merge delta has no actionable findings. |
| Repository cleanup | No merge markers; `git diff --check` clean. Owned test servers and tool browser stopped. |

Offline HTTP fixtures are test-only and do not prove a live PostgreSQL connection or hosted MCP access. No local catalog fallback exists in production.

## Operational handoff

Use [deployment setup](../../../docs/deploy-flow.md#products-đọc-dữ-liệu-postgresql-hiện-có) and the [API preflight](../../../services/shopops-api/README.md#read-only-deployment-preflight) before accepting a live deployment. Existing database host, database name, TLS and credentials remain operator-owned runtime configuration. User explicitly selected preparation without live inspection.

The AI engineer owns per-user registration, sandbox/team lifecycle, vault credentials and real MCP transport. The current four closed agent tools provide fixture aggregates/context; executable catalog/raw/pull-latest tools are not added by this policy change. Reconcile real granted schemas with validation, routing, authorization and tests as described in the [integration contract](../../../services/agent-core/contracts/product-investigation.md).

Every document uses its first successful mailbox read as a baseline. Under the existing latest-event contract, that first read cannot distinguish an old stored event from an event issued during a preceding outage; subsequent higher IDs navigate normally.

Docs impact: major—product behavior, API/config contracts, deployment route and agent integration seam updated. Local technical journal retained; AgentWiki publish skipped.

Unresolved questions: none for this scope. Live configuration/preflight and AI engineer MCP capability integration remain follow-up execution work.
