---
title: Product workspace and persistent catalog route
date: 2026-10-31
summary: "Implemented product evidence UI, versioned MCP investigation policy and PostgreSQL15432 deployment preparation; integrated current develop."
---

# Product workspace and persistent catalog route

## What happened
Built a Shopee-inspired inspection workspace with product gallery/detail, source-backed reviews/orders/returns, two-second active-view polling and direct browser navigation. The API reads persistent source records through cronjob HTTP, checks current access/revisions and caches only an unchanged authorized shop revision. Product image URLs pass through when available; missing media remains a placeholder.

The first independent review caught retained evidence after access failures and repeated full-history reads during polling. Typed access errors now clear retained state, and revision-aware caching rechecks current access before reuse. A browser regression also exposed old mailbox events overriding explicit product URLs; direct document entries now establish a first-read baseline. The contract limitation during an initial mailbox outage remains documented.

Integrated develop082006d after PR12/14 merged during implementation, resolving two UI source conflicts while retaining the new chat bridge, Connections default and Products independence from demo flags.

## Decision
Added opt-in returns-hosted-v2 with immutable agent bundle1.1.0. Instructions require scoped mart-first evidence and only backend-granted raw/refresh capabilities; no new executable transport/tool contract is claimed. AI engineer retains per-user identity, sandbox/team, vault and real MCP ownership.

User specified the existing PostgreSQL listener15432 and selected deployment preparation without live inspection. The API container defaults to source mode, requires explicit backend URL/identity and includes aggregate-only read-only catalog preflight. Both data services accept the15432 override offline; real App Configs and database access were not inspected. No data reset, credential access or deployment performed.

## Verification
API109 tests, web68 tests plus lint/build, agent487 passed with2 live suites skipped, and21 integrated browser tests passed. Independent final review found no actionable issues. Responsive rendered states inspected. No feature commit/push/deploy requested. Durable setup and integration decisions live in docs/deploy-flow.md and services/agent-core/contracts/product-investigation.md; see plans/261031-product-investigation/reports/delivery-verification.md for full evidence.

## Next steps
At deployment, apply existing runtime mappings and POSTGRES_PORT=15432 for source/processor, then run python -m app.catalog_check inside the configured API runtime. AI engineer can connect registered MCP schemas and identity credentials independently. Live acceptance remains pending by scope. AgentWiki publish skipped; local journal only.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
