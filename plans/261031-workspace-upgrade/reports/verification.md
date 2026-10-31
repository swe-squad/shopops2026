# Workspace upgrade verification

Date: 2026-10-31. Worktree: `/private/tmp/shopops2026-shopops-web`; branch: `codex/shopops-web`.

## Delivered behavior

- Three independently built frontend documents. Viewer has no credentials, business API, or shared client state. Separate operations/chat APIs retain their own SQLite persistence.
- Viewer fits one dynamic viewport. Desktop shows browser and phone together; narrow layouts switch visibility without remounting either client. Only child content scrolls.
- Browser tabs add/select/close with independent history, address, drafts and reload. Keyboard Arrow/Home/End/Delete behavior and active-tab link delivery are covered.
- Telegram-style conversation: compact identity/menu, date pills, tailed incoming/outgoing bubbles, quiet wallpaper, Message composer and paper-plane send. Actual timestamps; no fabricated presence/read receipts or inactive attachment/voice controls.
- Safe Markdown, horizontal table/code scrolling, streaming, reader-position preservation, explicit stop/history recovery. Chat links reach the active browser tab through the real operations mailbox.
- Reduced viewer/header height, removed duplicate headings/navigation bands, decorative footers and status bar. Interactive controls stay at least 44px; mobile inputs remain 16px.
- Canonical brand sync and drift check; typed API/error/SSE contracts; documented extension and integration boundaries; dedicated browser CI.

## Service verification

| Service | Passing tests | Other checks |
| --- | ---: | --- |
| shopops-web | 19 | Full `make ci`; final footer-only follow-up: 10 focused tests, lint and production build |
| shopops-chat | 42 | Final full tests, lint, TypeScript and production build |
| shopops-workspace | 51 | `make ci` |
| shopops-api | 31 | `make ci` / Ruff |
| shopops-chat-api | 53 | `make ci` / Ruff; 12 submission-boundary regressions |

Total: 196 service tests. No skipped/disabled assertions or retry-based acceptance.

`node scripts/sync-brand-assets.mjs --check` passes. `git diff --check` passes. Workspace workflow YAML parsed and independently reviewed; remote GitHub Actions was not run.

## Browser verification

Authoritative command: `npm test` in `tests/workspace`, using the pinned Chromium headless shell 156.0.8078.4 (v1248), matching the existing CI configuration. Final full suite: **12 passed in 30.3s**. Three real frontends and both real APIs; disposable SQLite databases. Only the upstream provider transport uses explicit offline fixtures, never imported by deployed services.

The original 11-test suite passed after layout/scroll repairs. The final Telegram pass added a twelfth test: multiline composition, one Enter submission, focus retention, menu keyboard navigation/Escape/outside dismissal, history refresh preserving a draft, and lock. The same assertions also check hidden-frame dimensions and keyboard exclusion.

Bounded phone stability check: `npm test -- --grep 'parent stays fixed at 375' --repeat-each=100 --max-failures=1 --reporter=dot --output=/private/tmp/shopops-ci-phone-probe` — **100 passed in 3.6m**, exit 0. Default pinned CI browser, unchanged real clicks/assertions, zero retries. This is finite regression evidence, not a guarantee against every intermittent browser failure. Preserved runner status: [full suite](full-suite-last-run.json), [phone repeats](phone-repeat-last-run.json).

Viewport matrix: 375×812, 768×1024, 1280×720, 1440×900, 844×390. Assertions check document bounds, parent-wheel immobility, critical controls, frame bounds, origin isolation, independent reload, active-tab link delivery and internal scrolling. Wide Markdown is tested with actual horizontal keyboard scrolling.

The controller also used the user's Edge browser: unlocked each app independently, added a temporary incident, switched tabs with an unsaved draft, checked timestamps, sent a fixture chat message and opened its link in the browser app. Temporary review tab closed afterward.

## Issues found

1. Streaming scroll race: a token-driven end-scroll occurred before the compositor delivered an upward wheel event, leaving the reader 32px away from their intended position. Observe upward wheel/touch/keyboard intent before native scrolling; retain native defaults. Browser and focused regression tests verify position retention and jump-to-latest.
2. SQLite timestamp interpretation: timestamps without offsets represent UTC; normalize before local display. Regression tests verify explicit offsets, naive UTC and invalid values.
3. Provider submission boundary: persist uncertain-send intent immediately before input POST, after opening a follow-up event stream. Only confirmed 2xx acceptance permits cancellation. Failed GETs are retryable; ambiguous input POSTs remain pending without automatic resend. Redirect responses are rejected. Twelve regressions and independent re-review pass.
4. Test fixture recovery was incomplete: stopping an already-streaming reply reaches session/turn reads. Added those fixture endpoints and kept the stronger stop test; no production workaround.
5. Brand drift was manual-only: the new workflow now runs drift and browser checks for relevant service/asset/tooling changes, with read-only permissions and no credentials.
6. Installed-Chrome headless compatibility: the phone browser unlock failed on repetition 25; the parent received a click targeted at an iframe, while the browser child received no pointer/click/submit. Keeping layout initially passed 30/30 but did not resolve the full-suite failure. A no-switch control passed 30/30. Enlarging the native window from 500×812 to 1280×1024 while preserving the emulated 375×812 viewport passed 30/30. This supports a browser-channel/native-window routing hypothesis, not proof of a specific engine defect. The pinned CI browser passes the unchanged full suite; optional installed-Chrome emulation remains a documented compatibility caveat. [Diagnosis](iframe-input-diagnosis.md), [Playwright browser modes](https://playwright.dev/docs/browsers#google-chrome--microsoft-edge).

The viewer retains overlapping panels with visibility/pointer rules to preserve each client's viewport dimensions. This is a layout/state invariant, not a claimed cure for the installed-Chrome behavior. Regression checks verify retained bounds and exclusion from keyboard navigation.

## Visual review

Final render-check artifacts: [viewer](render-viewer.json), [browser](render-browser.json), [chat](render-chat.json). Each runs at 375×812, 768×1024 and 1440×900. Viewer/browser: zero findings. Chat: no findings at phone/tablet; one `main-narrow` heuristic at desktop because its intentional mobile layout is capped at 640px (638px inner width). This is documented, not suppressed; stretching the standalone mobile app would conflict with the accepted design.

Populated screenshots and menu/recovery states are under `screenshots/`. Hover/focus/disabled/empty/error states were inspected. Physical mobile keyboard behavior remains outside this local verification.

Three weakest earlier areas were hierarchy, spacing and Telegram fidelity. Removed redundant title/footer bands, reduced chrome/padding, and replaced generic assistant cards/header with a recognizable conversation layout.

| Design rubric | Score / 2 | Visible evidence |
| --- | ---: | --- |
| Brief fidelity | 2 | [Desktop](screenshots/workspace-desktop.png): warm, calm, practical; independent browser window beside phone conversation |
| Hierarchy | 2 | Compact chrome; page task and chat messages dominate; one send action |
| Spacing rhythm | 2 | Tight toolbar groups; larger separation between app surfaces; removed duplicate footer/title bands |
| Alignment | 2 | Page/form edges align; bubbles separate incoming and outgoing messages |
| Typography | 2 | System sans with code mono; compact16px chat identity and readable message text |
| Color discipline | 2 | Orange identifies actions/current state; ivory/white carry content |
| Depth and shape | 2 | Quiet borders/rounding; tailed message bubbles; menu uses restrained elevation |
| States and feedback | 2 | [Menu](screenshots/chat-menu.png) focus/hover, disabled send, empty records and [recovery](screenshots/chat-recovery.png) inspected |
| Responsiveness | 1 | Five browser viewport sizes covered; physical mobile keyboard/touch not verified |
| Generic-design avoidance | 2 | Real tab controls and conversation affordances; no KPI placeholders or decorative feature grid |
| Content and copy | 2 | Honest disconnected/empty states; test records visibly labeled; no invented business metrics |
| Craft details | 1 | Brand favicon/assets and consistent client SVG controls; viewer utility arrows still use text glyphs |

Total: 22/24. Remaining deductions are explicit; no claim of physical-device certification or pixel-identical Telegram reproduction.

## Review and extension pattern

Independent review closed the provider boundary and CI findings. A second review of Telegram menu/date/composer changes found no actionable issue; 23 focused tests also passed independently. The narrow-viewer retained-layout change was reviewed separately with no actionable finding. Follow-up review corrected stale report wording after the installed-Chrome hypothesis was revised. The simplifier made scoped CSS cleanup only; behavior and styling preserved.

Docs impact: major. [Feature development](../../../docs/feature-development.md) owns client/viewport/brand/test extension rules. [Backend integration pattern](../../../docs/service-integration-pattern.md) owns route/application/adapter/storage boundaries and recovery/identity limitations. Owning service READMEs/AGENTS were aligned with the current brand and behavior.

## Limits and handoff

- No live OpenAI credentials or account access tested; no live shop integration or fabricated production records.
- No deployment, container build or deployed CSP verification. External websites may prohibit iframe embedding; Open in new tab remains available.
- One workspace token and one SQLite-backed instance per API; production identity, multi-tenancy and scaling remain separate integration work.
- Files remain uncommitted in the feature worktree. No push or deployment. Unrelated `.serena/` and the brand journal were preserved.
- Installed Chrome full-headless phone emulation retains the observed compatibility caveat above. No app origins, real clicks, assertions, or retry policy were changed to hide it.
- Local [journal](../../journals/2026-10-31-shopops-independent-client-upgrade.md) records the completed evidence; AgentWiki publishing skipped.
- Process audit: ports 5173–5175 and 8000–8001 have no listeners. Final test-stack PIDs 77425, 77438, 77472, 77493 and 77514 are absent. Managed test sessions exited; previous review/probe servers were also stopped.

Unresolved product decisions: none for the accepted interface/integration-foundation scope. Installed-Chrome emulation and untested live/deployed environments remain the explicit limitations above.
