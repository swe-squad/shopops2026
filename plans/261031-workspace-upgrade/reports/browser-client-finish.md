# Browser client completion

Status: DONE · 2026-10-31

Completed the saved browser upgrade under `services/shopops-web/` without modifying other clients,
backend services, viewer code, or integration tests. No server or background process started.

## Changes

- Fixed the tab action union so the production TypeScript build narrows navigation correctly.
- Preserved mounted per-tab shop content, draft fields, address state, history, and external iframe.
  Added interaction coverage for adding/selecting/closing tabs, keyboard focus and wrapping,
  Home/End/Delete, last-tab replacement, and active-tab mailbox delivery/deduplication.
- Limited incident deep-link scrolling to `.shop-page`. Switching back to a deep-linked tab no
  longer resets the reader's scroll position.
- Derived incident loading from the completed request rather than synchronously resetting state
  in an effect. Covered response validation/retry, stale read versus save, duplicate-save blocking,
  and aborting pending reads/writes when the owning tab unmounts.
- Replaced the service's Notion/blue default guidance with canonical ShopOps brand references,
  vendored asset sync/check commands, viewport/scroll boundaries, and independent-client rules.
- Normalized offset-free incident timestamps as UTC before local display and ISO `dateTime`
  rendering. The API wire contract remains unchanged; timezone regression cases cover naive,
  UTC, and explicit-offset values.
- Prioritized interaction space with a 48px app header, one shop navigation row, smaller headings,
  tighter spacing, and no redundant title, footer, or browser status bands. Controls retain 44px
  targets; narrow-screen inputs use 16px text. The 100-record note appears only for a 100-record feed.

## Verification

From `services/shopops-web`:

- Full suite after timestamp and compact-layout changes: 5 files, 19 tests passed. The timezone
  regression also passed with the test process launched under `TZ=UTC`.
- Final footer/status removal: `npm test -- src/browser-pane.test.tsx src/incident-feed.test.tsx`,
  10 focused tests passed, including the new conditional 100-record note.
- Final `npm run lint`: passed, no warnings.
- Final `npm run build`: passed (TypeScript + Vite production build).

From repository root:

- `node scripts/sync-brand-assets.mjs --check`: passed, all three clients matched.
- `git diff --check -- services/shopops-web`: passed.

Docs impact: minor, updated the owning service README and AGENTS.

Controller reports 11 browser integration tests passed after the final browser layout; an additional
Telegram-style chat pass is in progress. Viewport and visual evidence remain controller-owned.
External previews may be blocked by the destination's embedding policy; the external-open control
remains available.

Unresolved questions: none.
