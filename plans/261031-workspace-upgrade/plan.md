---
title: ShopOps interface upgrade
description: Independent browser and Telegram-style clients in a fixed branded viewer
priority: high
status: completed
---
# ShopOps interface upgrade

Started: 2026-10-31. Status is recorded in frontmatter; progress is tracked in the phase checklists.

## Outcome and boundaries

Upgrade the accepted two independent apps in one viewer using the landed ShopOps brand. The parent occupies one viewport and never needs scrolling; browser content and chat messages own their scrolling. Desktop shows a working browser tab window beside a Telegram-style phone client. Narrow screens switch the visible client without resetting either app. Keep separate origins, builds, tokens, state and backend engines.

Interface and integration foundation only. No production deployment, credentials, fabricated shop data, new platform integration, or shared client runtime. Existing backend contracts remain compatible. Do not weaken, remove or skip failing checks to satisfy the goal.

## Design brief

- Register: Product.
- Scene: A seller checking shop issues and asking the operations companion for help from a laptop; calm, warm and practical.
- Direction: Clarity in the chaos, from the accepted brand kit.
- Color: Restrained; warm ivory #F9F6F0, charcoal #1C1B1A, brand orange #F4511E, accessible action orange #B5310B. Canonical tokens in docs/brand/assets/tokens.
- Type: Inter/system sans with mono only for code; hierarchy through weight and spacing.
- Signature: A real browser window alongside a quiet phone-shaped conversation, with the interlocking ShopOps mark.
- Dials: variance 3, motion 2, density 6.

## Phases

The accepted architecture, brand assets and existing worktree were inspected before assigning disjoint owners. Phase checklists are tracked in the owning files:

1. [Implement viewer and client refinements](phase-01-interface.md).
2. [Verify integration foundation and establish extension pattern](phase-02-integration.md).
3. [Exercise, analyze and repair](phase-03-validation.md); independent review and final diff.

## Acceptance

- Parent scrollWidth/scrollHeight stay within viewport at 375×812, 768×1024, 1280×720, 1440×900 and short landscape sizes; no clipped critical controls.
- Both child documents remain independent and mounted across layout/view changes. Reload affects only the chosen child.
- Browser tabs add/select/close; tab histories and local form state survive switching. Keyboard controls and visible focus work.
- Chat composer/header stay available, messages/tables/code scroll internally; streaming respects reader position, interruption/retry remain explicit and safe.
- Navigation through a chat link reaches the active browser tab through the real operations API, never the parent URL or chat origin.
- Canonical brand assets are applied consistently with deterministic sync/drift checks.
- All five service tests/lint/build where applicable pass; repeatable browser tests and visual inspection verify the final interfaces.
- Future-feature guide identifies ownership, API and adapter contracts, validation commands, extension steps and real integration limitations.

## Ownership

Controller: viewer, shared asset-sync tooling, browser integration suite, cross-service docs and coordination.
Browser worker: services/shopops-web/**.
Chat worker: services/shopops-chat/**.
Backend worker: services/shopops-api/**, services/shopops-chat-api/**, docs/service-integration-pattern.md.

Existing unrelated .serena and brand journal files stay untouched. Worktree: /private/tmp/shopops2026-shopops-web; branch: codex/shopops-web.
