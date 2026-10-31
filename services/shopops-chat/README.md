# ShopOps chat

Standalone mobile-friendly web app with a Telegram-style conversation. Open it directly, or display its complete document beside the independently hosted [shop browser](../shopops-web/README.md) in the presentation-only workspace viewer. Each app has its own entry point, build, hosting configuration, and in-memory access token. The viewer does not import app components or receive credentials.

## Local development

1. Start the operations API on `127.0.0.1:8000` and chat API on `127.0.0.1:8001`; see their READMEs.
2. Run `npm ci` then `npm run dev` here. This app uses port **5174** and refuses to switch ports.
3. Open the shop browser separately on port **5173**. Unlock both apps with the same workspace token.

Chat history and streaming requests go to same-origin `/api/chat/messages`. Clicking a message link sends an authenticated `POST /api/operations/navigation` with `{url}`. The browser app polls that operations endpoint and opens the newest link. `/shop/...` links stay relative until the browser app resolves them against its own origin. If delivery fails, Retry opening link retries only navigation, never the chat turn. Keep the shop browser open and unlocked to receive links.

Replies support safe Markdown tables, code, lists, quotes, and URLs. Raw HTML is ignored; remote images are represented as text and never loaded. Stopping or interrupting a reply keeps its partial content and requires loading server history before another turn, avoiding an automatic duplicate submission. Tokens stay only in app memory until lock or reload; OpenAI credentials belong only to the chat API.

## Conversation and brand

The conversation uses a compact ShopOps contact header, round avatar, soft incoming/outgoing bubbles with tails, and a pill composer with a paper-plane send button. Day separators and message times come from actual timestamps in your local time. The header shows only the assistant's role or real loading/typing/recovery state. There are no implied online/read receipts or inactive attachment and voice controls.

Open **Chat menu** for **Load conversation** or **Lock**. Arrow keys, Home/End and Escape work in the menu; Escape restores trigger focus, and clicking or tabbing outside dismisses it. Reload is disabled during loading/streaming. Recovery remains directly accessible beside the composer after an interruption.

The signed-in document stays within one viewport. A compact header and composer leave space for the `Conversation` log to scroll. Wide Markdown tables and code have their own keyboard-accessible horizontal scroll regions. Incoming replies follow the bottom only while you are near it; reading earlier messages keeps your position and exposes **Jump to latest**. A new-content label signals incoming text below. Submitting your own message or explicitly loading history returns to the latest content.

The composer grows up to a bounded height, retains a follow-up draft while a response streams, and supports Enter to send or Shift + Enter for a new line. Enter during input-method composition does not send. **Stop response** preserves partial content and requires **Load conversation** before another turn. Link-delivery notices can be dismissed; retrying a failed link only retries navigation.

The layout uses safe-area padding, 44px or larger primary touch controls, visible keyboard focus and reduced-motion styles. Standalone pages follow the visual viewport while the keyboard is visible; pinch zoom remains browser-controlled. Embedded clients follow their iframe size. Dynamic viewport height provides a fallback when the visual viewport API is unavailable. Phone browser emulation is covered; physical-device keyboard behavior is not claimed as verified.

UI follows the [ShopOps brand direction](../../docs/brand/brand-direction.md) and [design guidelines](../../docs/brand/design-guidelines.md). The app loads vendored canonical tokens, mark and app metadata from `public/brand/`. After changing the source brand kit, run `node scripts/sync-brand-assets.mjs` from the repository root; `node scripts/sync-brand-assets.mjs --check` verifies parity across the independent clients. Use ink for body text and accessible action orange for links and primary buttons.

## Validation

`make ci` installs the lockfile, runs lint and tests, and builds this app independently. Transport tests cover fragmented UTF-8/SSE frames, provider errors, truncation, cancellation, and terminal events. Interaction tests cover Markdown/link delivery, explicit recovery, stopping, locking, app isolation, reader-preserving scrolling/resizing, draft/input behavior, and standalone versus embedded viewport handling. The repository browser suite checks real document geometry and API integration; see [workspace architecture](../../docs/client-workspace.md).

## CapRover

The container listens on port **80**. Configure both runtime upstreams before starting:

- `API_URL=http://srv-captain--shopops-api-dev:8000`
- `SHOPOPS_CHAT_API_URL=http://srv-captain--shopops-chat-api-dev:8000`

Use corresponding app names without `-dev` in production. Keep backend services internal, enable HTTPS on this frontend, and leave `VITE_API_BASE_URL` unset. nginx disables buffering and caching for streamed chat replies. Missing upstream variables fail startup. Service discovery and shared CI/deployment use this app's `service.json`.

Set optional `WORKSPACE_VIEWER_URL` to the viewer's exact HTTPS origin to permit embedding through CSP `frame-ancestors`. Blank permits self framing only. Vite permits the local viewer on port 5175. Unlock remains local to this client, whether opened directly or embedded.

See [workspace architecture](../../docs/client-workspace.md) for the two-app boundary and full setup. No deployment or live provider credentials are configured by this change.

## Core demo chat

The API's public auth config selects the existing workspace-token form or one demo phone login
without OTP. The synthetic number is configured server-side; browser input cannot select an
owner, shop, Core token or provider. Sessions stay in memory and clear on lock/reload.
Report mode and attachment controls appear only when authenticated capabilities support them.
Downloads fetch with the session token into a bounded, hash-checked Blob and revoke its URL;
attachments never pass through the shop-browser navigation mailbox.

In Core demo mode, normal shop links use authenticated `/api/chat/navigation`; the chat backend
holds the operations workspace credential. The shop browser still unlocks independently.
Stop means stop viewing: Core may continue running. Load history explicitly before another
message after interruption; reload never silently resends input. Legacy chat remains supported.
