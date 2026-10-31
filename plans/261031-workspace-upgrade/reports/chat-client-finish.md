# Chat client completion

Status: DONE · 2026-10-31

Scope: `services/shopops-chat/**` in `/private/tmp/shopops2026-shopops-web`. No changes to sibling services, viewer, E2E tests or shared scripts. No servers or commits created.

## Result

- Standalone Telegram-style client uses canonical ShopOps mark, tokens, favicon and metadata. Header and composer remain outside the single `role="log"` named `Conversation`.
- Latest user-directed Telegram pass uses a 16px contact name, circular avatar, real loading/responding/assistant status, a functional overflow menu, soft tailed incoming/outgoing bubbles, bottom-right timestamps, and local subtle wallpaper. Actual message dates produce Today/date separator pills; repeated adjacent dates share one separator. Pill composer uses a paper-plane send action.
- Final density pass removes the decorative conversation label/empty-state mark, excess bottom padding and visible footer hint. Compact header/composer keep 44px controls and safe areas; keyboard guidance stays available to screen readers.
- Message tables/code have independent horizontal scroll regions and keyboard focus. Raw HTML stays disabled, remote images remain text, and links use authenticated navigation delivery.
- Scroll follows the bottom, respects earlier-message readers, exposes new-content/Jump to latest, and handles content/viewport resize. Upward wheel/touch/keyboard intent pauses following before native scroll events arrive.
- Composer preserves queued drafts during streaming; Enter sends, Shift+Enter inserts a line, input-method composition does not send. Stop preserves partial text and requires explicit history loading; navigation retry never resends a turn.
- Removed redundant history button from the scrollable error bubble. History reload and Lock live in Chat menu; recovery beside composer is `role="group"`, accessible name `Conversation recovery`.
- Standalone unzoomed page follows visual viewport. Embedded client follows iframe. Safe areas, dynamic-height fallback, reduced motion and short-height rules preserved.

## Telegram design brief and interaction checks

- Register: Product.
- Scene: Seller working through one operations conversation on a phone or alongside the shop browser; calm and familiar.
- Direction: Telegram-style one-to-one conversation, explicitly requested by the user; retain ShopOps identity and independent backend.
- Color: Restrained; canonical ivory/ink/action orange, tinted outgoing bubbles, white incoming bubbles.
- Type: Existing Inter/system sans; compact 16px contact name, 15px messages and 16px inputs.
- Signature: Round ShopOps avatar, tailed bubbles and paper-plane composer on subtle local wallpaper.
- Dials: variance 3, motion 2, density 7.

Reference context: [Telegram's February 2026 Android redesign](https://telegram.org/blog/crafting-android-design-and-more). Scope is this single conversation; no extra app navigation, fabricated online/read receipts, attachment/voice controls or Telegram integration.

`chat-actions-menu.tsx` supports ArrowUp/Down, Home/End, Escape with trigger focus return, and outside-pointer/focus dismissal. Reload is disabled during loading/streaming; Lock remains available. All actions call existing controller behavior. Four menu tests cover these paths; date tests cover actual local-day labels, past years, invalid timestamps and adjacent-day grouping.

Read-only Chrome checks after the visual pass used the running frontend previews with APIs intentionally stopped: recovery/menu states at 375×812, 768×1024 and 1440×900 stayed exactly inside the viewport; composer/send controls were 44px high. Arrow navigation, Escape focus return and native Tab dismissal to Conversation log passed; no runtime errors. Expected history 502 was from absent fixture API. Full populated-conversation screenshots and final matrix belong to controller's clean-stack E2E pass. Mobile-width max 640px on large standalone screens remains intentional.

## Scroll diagnosis and regression

Root browser test reproduced upward wheel landing at `scrollTop=32`, then staying there. Instrumented local Chrome confirmed the race:

1. At 1837.5ms, streamed line added 32px. Hook wrote end from 2724 to 2756 (`scrollHeight=3299`, `clientHeight=543`).
2. At 1837.9ms, asynchronous compositor wheel arrived using its old offset; observed position was 32.
3. Existing `onScroll` only then disabled following.

Repair: local non-passive wheel/touchmove listeners observe upward intent before native scrolling is applied; no `preventDefault` or custom wheel scrolling. Keyboard PageUp/Home/ArrowUp/Shift+Space intent shares the pause. Downward movement and multi-touch stay native. Cleanup removes every listener and ResizeObserver.

Regression before fix: delayed-scroll test expected 600, got 632. After fix: all intent, direction, native-default, resize and cleanup tests pass. Real Chrome repeated three streamed turns; position remained exactly 0 through completion, and Jump to latest returned within 1px of the bottom every time. Temporary probe browser contexts closed. Only the existing test stack and explicit test-only provider/database were used.

## Verification

- `npm test`: 42 tests across 8 files passed after Telegram refinements.
- `npm run lint`: clean, no warnings.
- `npm run build`: TypeScript and Vite passed; JS 400.03kB / 123.20kB gzip, CSS 14.10kB / 3.39kB gzip.
- `git diff --check -- services/shopops-chat`: clean.
- `node scripts/sync-brand-assets.mjs --check`: canonical parity for all 3 independent clients passed.
- Local source/diff review: no new shared app state, credentials, network contracts or remote media loads. Build/deployment manifests unchanged.

Docs impact: minor. Service README and AGENTS now describe actual brand source, Telegram conversation/menu patterns, timestamp-derived day labels, scroll ownership, recovery, mobile behavior and checks. Inherited Notion document retained as template history; it is no longer the service UI authority.

## Controller follow-through

- Run clean-stack E2E and final viewport/visual matrix; controller owns those suites. Targeted Chrome scroll evidence above already verifies this repair.
- Scope recovery action with `getByRole('group', { name: 'Conversation recovery' }).getByRole('button', { name: 'Load conversation' })`.
- Header actions: open `getByRole('button', { name: 'Chat menu' })`, then `getByRole('menuitem', { name: 'Lock' })` or `Load conversation`.
- Earlier diagnostic probes used only temporary test data; all probe browser contexts closed. Fresh E2E lifecycle creates a clean database.
- Physical-device keyboard behavior remains unverified; README states that limit. No production provider call or deployment performed.

Unresolved questions: none for this service scope.
