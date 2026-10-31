# Test, analyze, upgrade

Run service checks after changes, then a repeatable Playwright suite against three real frontend documents and isolated real APIs. Use clearly labeled test-only provider event fixtures for rich streaming, never shipped demo business data. Use temporary SQLite files and deterministic ports; fail if ports belong to another process, stop owned processes after tests.

Assert parent does not scroll, child scrollers move, controls remain available, keyboard navigation works, tab state survives, narrow view switching preserves sessions, reload is independent, unsafe URLs stay rejected and cross-origin access is blocked. Exercise real navigation persistence, backend failures and interrupted chat streams.

Capture desktop/tablet/phone and short-height layouts; run the frontend design render checker and inspect screenshots. Repair concrete issues, rerun affected checks, and obtain independent review. Record commands/results/limitations in reports; do not claim live OpenAI or Docker validation without running them.

## Acceptance checklist

- [x] Affected service tests, lint/build, brand drift and diff checks pass.
- [x] Cross-app browser matrix, real API navigation, streaming/recovery, keyboard and isolation checks pass.
- [x] Visual artifacts, justified checker exception and independent review recorded.
- [x] Owned processes stopped; final evidence, plan and local journal reconciled.

Evidence: [verification report](reports/verification.md).
