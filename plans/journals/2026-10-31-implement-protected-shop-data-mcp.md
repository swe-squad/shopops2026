---
title: Implement protected shop data MCP
date: 2026-10-31
summary: "Added PostgreSQL-backed MCP tools, scoped authorization, integrations and engineer handoff"
---

# Implement protected shop data MCP

## Result
Implemented the MCP side of the data boundary with the official Python SDK: catalog, mart/raw SQL, grant-bound temporary results, automatic bounded refresh and operation tracking. Mounted operator JSON defines credentials, catalog and shop mappings. Upstream integrations remain explicit external contracts.

## Verification
make ci passed with 107 tests and one database check skipped without a DSN. The complete suite passed 108 tests against a disposable PostgreSQL instance, which was stopped afterward. Checks include two-shop RLS, protected columns, result ownership, saved results, idempotency records, real MCP client calls and signed JWT validation. Docker image was not built because no local Docker daemon is running.

## Next
Data engineer supplies real views/RLS, catalog and TLS/credential configuration. Identity/approval and collection/processing services implement HANDOFF.md. Verify their live behavior and deploy dev before declaring operational readiness. AgentWiki publish skipped.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.

Final verification after review fixes: Ruff lint/format passed; 145 unit/protocol tests passed with one database test skipped without DSN; the complete suite passed 146 tests against a disposable PostgreSQL instance. That instance was stopped afterward. Strict response schemas and UTC-idempotency regressions are included.
