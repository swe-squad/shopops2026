---
title: ShopOps independent-client upgrade
date: 2026-10-31
summary: "Delivered compact independent browser and Telegram-style clients, verified integration foundations, and documented extension patterns."
---

# ShopOps independent-client upgrade

## Result

Upgraded the accepted viewer on `codex/shopops-web` in `/private/tmp/shopops2026-shopops-web`. One fixed viewport shows an independent browser window beside a standalone Telegram-style mobile app. Child content owns scrolling. Narrow layouts preserve both mounted clients and their viewport dimensions. Compact chrome prioritizes the user's working space.

Browser tabs retain independent histories, addresses and drafts. Chat now has a compact contact header, keyboard-accessible overflow menu, date dividers, tailed bubbles, quiet wallpaper, a fixed Message composer and paper-plane send. Streaming Markdown, tables, code, link delivery, reader-position retention and explicit recovery remain functional. Separate builds, origins, authentication and persistent APIs are preserved.

## Verification

- 196 service tests passed across five services, with lint, type checks and production builds as applicable.
- Pinned CI Chromium: 12 browser scenarios passed in 30.3s; bounded phone case 100/100 passed in 3.6m, zero retries.
- Five viewport sizes, keyboard/tab state, child-only scrolling, real API navigation, stream stop/recovery and isolation covered.
- Brand drift and diff checks passed. Visual review 22/24; desktop chat-width heuristic documented because the standalone client intentionally retains mobile proportions.
- Independent review and scoped simplification completed. Local documentation links checked.
- All five test ports cleared; owned server processes exited. No background preview left running.

## Defects and decisions

Fixed a streaming auto-scroll race by observing upward input intent before native scrolling. Corrected naive SQLite UTC timestamps before local display. Tightened provider submission boundaries: ambiguous sends stay pending, confirmed acceptance owns cancellation, failed stream setup remains retryable.

Installed Chrome full-headless phone emulation showed an intermittent native iframe click-routing failure. Visibility styling did not establish a cure. No-switch and enlarged-native-window controls each passed 30/30; the unchanged pinned CI browser passed the full suite and 100-repeat phone check. Keep this a documented compatibility hypothesis, with no origin changes, forced clicks, weakened assertions or retry-based acceptance.

## Handoff

Docs impact: major. [Feature patterns](../../docs/feature-development.md), [backend integration patterns](../../docs/service-integration-pattern.md), and [verification evidence](../261031-workspace-upgrade/reports/verification.md) record ownership, extension rules, commands and limitations.

No live OpenAI credentials, deployed environment, Docker build or physical mobile keyboard certification tested. Backend adapters are ready for integration within the documented single-workspace/single-instance boundary. Changes remain uncommitted; no push or deployment. Unrelated files preserved. AgentWiki publishing skipped; journal is local.

Unresolved product decisions: none for the accepted interface and integration-foundation scope.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
