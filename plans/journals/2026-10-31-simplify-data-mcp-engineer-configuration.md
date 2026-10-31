---
title: Simplify data MCP engineer configuration
date: 2026-10-31
summary: Separate the dataset catalog from secrets and document safe tool extensions
---

# Simplify data MCP engineer configuration

## Result
Added optional MCP_CATALOG_FILE so data engineers can maintain approved metadata separately from operator credentials and shop allowlists. Inline catalogs remain supported; ambiguous sources and unknown fields fail closed. Added model-derived editor schemas, Make preflight shortcuts, raw window validation and safe diagnostics.

DEVELOPMENT.md maps data/tool changes to implementation and tests and gives a protected tool-extension example. README, handoff and deployment config navigation now point to the split examples.

## Verification
Ruff lint and formatting passed. Service suite: 155 passed with one database check skipped without a DSN; a subsequent full run against disposable PostgreSQL passed all 156 tests and stopped its server afterward. Separate schema exports parsed as JSON and the split example passed configuration preflight. No database query/authorization path changed, and no deployment or real credentials were accessed.

Independent review found a stale deployment step omitting the catalog mount; it now specifies both file variables and the legacy inline alternative. A scoped simplification pass made no changes.

## Next
Update PR #3 and let the engineer use the catalog and development guide for wiring real data. Live identity, approval, job integration and deployment gates remain. AgentWiki publish skipped.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
