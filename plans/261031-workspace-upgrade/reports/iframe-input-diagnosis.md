# Phone iframe unlock investigation

2026-10-31. No repository source or existing test files modified.

Status: native iframe input-routing failure confirmed. The initial visibility-only fix was not
reliable; a later full-suite run reproduced the symptom with that change in source. Browser-channel
and native-window geometry are the current cause-aligned hypothesis. Bundled headless-shell parity
verification is handed to the controller.

## Observed failure

Exact 375×812 viewport flow with passive document-level pointer/input/submit listeners reproduced
the failure on repetition 25: 24 passed, 1 failed, 5 not run after the first failure.

- Parent document received pointerdown, mousedown, pointerup, mouseup, and click with target IFRAME
  at (187.5, 742.37), inside the visible unlock button's correct frame-adjusted rectangle.
- Browser child received input and change only. No pointer, click, or submit event reached it.
- Chat child in the same run received BUTTON pointer/click and FORM submit normally.
- React's browser input update completed and enabled the submit button. No JavaScript error occurred.
- Empty chat history was sufficient; prior streamed-message/history load was not required.

This locates the failure before React form handling. It does not by itself distinguish iframe
reactivation from native/emulated viewport geometry or browser-channel behavior.

Evidence: `baseline-pointer-events.json` and
`baseline-results/unlock-probe-records-the-p-f14b3-urning-to-the-phone-browser-repeat24/trace.zip`.
Runtime: Playwright 1.64.1, installed Chrome channel, HeadlessChrome/156.0.0.0.

## Controlled comparison

Only injected viewer CSS changed before the exact flow:

```css
@media (max-width: 900px) {
  .workspace-grid > .client-panel { grid-area: 1 / 1; }
  .workspace-grid[data-active-client="browser"] .chat-panel,
  .workspace-grid[data-active-client="chat"] .browser-panel {
    display: grid;
    visibility: hidden;
    pointer-events: none;
  }
}
```

30/30 repetitions passed (1.3 minutes). Original input fill, real mouse click, and browser-address
viewport assertion were retained; no Enter substitution, retry, or added delay.
Each run also verified the inactive chat iframe retained width >300 and height >600, its region
was absent from accessible-role queries, and 20 native Tab presses never focused that hidden iframe.

This 30-run result was a false-positive indication of reliability: the controller's later full suite
failed the same 375px unlock after the visibility change was applied in source. That failure is
preserved in `visibility-source-failure/`. Do not cite this comparison as proof that visibility fixes
the native routing problem.

## Further controls

- No-switch control using the current source: 30/30 passed. This does not prove the switch is
  required, but the failure did not reproduce without it in this bounded sample.
- Native-window comparison using the current complete phone flow (including the hidden-frame
  bounds, focus/Tab, and wheel checks): 30/30 passed. Before navigation, CDP enlarged only the native
  window to 1280×1024. No CSS, origin, input method, retry, or near-click delay changed.
- `Browser.getWindowForTarget` confirmed initial physical bounds 500×812; the failure traces'
  native screencast measured 500×725. The unlock point at y742.37 lies below that recorded content
  height, while chat's unlock point at y661 lies above it.
- After enlargement, `Page.getLayoutMetrics` and window.innerWidth/innerHeight still reported
  exactly 375×812. Browser outerWidth/outerHeight and CDP window bounds reported 1280×1024.
- The latest failed source trace has no passive pointer instrumentation, so identical native event
  routing in that exact populated-history run is not independently proven. Its point and geometry
  match the instrumented baseline failure.

Primary-source context supports testing the browser channel before further product edits:
[Playwright viewport implementation](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/chromium/crPage.ts)
documents OOPIF routing problems outside the native window and applies window insets in headful mode.
[Playwright issue 33674](https://github.com/microsoft/playwright/issues/33674) records missing OOPIF
mouse events in full-headless Chrome while headed/headless-shell worked; it was closed for inactivity,
not with a claimed fix. These sources corroborate a hypothesis, not proof of this instance's internals.

## Reproduction configuration and commands

Working directory: `/private/tmp/shopops2026-shopops-web/tests/workspace`.

```sh
PROBE_MODE=noswitch npm test -- --config /private/tmp/shopops-unlock-probe/playwright.config.ts --repeat-each=30 --workers=1
PROBE_MODE=native npm test -- --config /private/tmp/shopops-unlock-probe/playwright.config.ts --repeat-each=30 --workers=1
```

The temporary config imports the repository's `tests/workspace/playwright.config.ts`, preserving
its deterministic local server/provider setup, base URL, and test settings. It overrides only
testDir, outputDir, list reporter, maxFailures=1, installed `channel: 'chrome'`, and
`trace: 'retain-on-failure'`. Outputs: `noswitch-results/` and `native-results/`. The companion
`unlock-probe.spec.ts` imports the unchanged real helpers. Both modes add passive document listeners;
native mode alone calls `Browser.setWindowBounds` after setting the 375×812 emulated viewport and
before navigation. The original native mouse click remains unchanged.

Limits: these bounded controls are not a guarantee against an intermittent failure. They used empty
chat history, while the controller's latest failed full-suite run had populated history. The first
failure log recorded target tag IFRAME without title/src, so it cannot independently identify which
iframe element received that parent event; later instrumentation records both fields but has not
captured a new failure. The screencast dimensions are a clue to the native content surface, not an
independent measurement of its hit-test region. No opacity, origin-change, or site-isolation bypass
was used.

Controller follow-up: the unchanged full suite subsequently passed **12/12** with the default pinned
Chromium headless shell, matching CI. The phone case then passed **100/100** in a bounded repeat run
with zero retries. See [final verification](verification.md) for commands and limits. This supports
using the configured CI browser for acceptance; it does not prove that installed-Chrome routing is fixed.

All owned test-stack PIDs were confirmed absent before handoff. Ports 8000, 8001, 5173, 5174, and
5175 were clear. Controller may now own a new parity-test stack.
