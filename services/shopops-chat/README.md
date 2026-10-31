# ShopOps chat

Standalone mobile-friendly web app with a Telegram-style conversation. Open it directly, or display its complete document beside the independently hosted [shop browser](../shopops-web/README.md) in the presentation-only workspace viewer. Each app has its own entry point, build, hosting configuration, and in-memory access token. The viewer does not import app components or receive credentials.

## Local development

1. Start the operations API on `127.0.0.1:8000` and chat API on `127.0.0.1:8001`; see their READMEs.
2. Run `npm ci` then `npm run dev` here. This app uses port **5174** and refuses to switch ports.
3. Open the shop browser separately on port **5173**. Unlock both apps with the same workspace token.

Chat history and streaming requests go to same-origin `/api/chat/messages`. Clicking a message link sends an authenticated `POST /api/operations/navigation` with `{url}`. The browser app polls that operations endpoint and opens the newest link. `/shop/...` links stay relative until the browser app resolves them against its own origin. If delivery fails, Retry opening link retries only navigation, never the chat turn. Keep the shop browser open and unlocked to receive links.

Replies support safe Markdown tables, code, lists, quotes, and URLs. Raw HTML is ignored; remote images are represented as text and never loaded. Stopping or interrupting a reply keeps its partial content and requires loading server history before another turn, avoiding an automatic duplicate submission. Tokens stay only in app memory until lock or reload; OpenAI credentials belong only to the chat API.

The layout uses dynamic viewport height, safe-area padding, a reachable composer, 44px or larger primary touch controls, keyboard focus, and a scrollable message list. Phone browser emulation is covered; physical-device keyboard behavior is not claimed as verified.

## Validation

`make ci` installs the lockfile, runs lint and tests, and builds this app independently. Transport tests cover fragmented UTF-8/SSE frames, provider errors, truncation, cancellation, and terminal events. Interaction tests cover Markdown/link delivery, explicit retry, stopping, locking, and app isolation.

## CapRover

The container listens on port **80**. Configure both runtime upstreams before starting:

- `API_URL=http://srv-captain--shopops-api-dev:8000`
- `SHOPOPS_CHAT_API_URL=http://srv-captain--shopops-chat-api-dev:8000`

Use corresponding app names without `-dev` in production. Keep backend services internal, enable HTTPS on this frontend, and leave `VITE_API_BASE_URL` unset. nginx disables buffering and caching for streamed chat replies. Missing upstream variables fail startup. Service discovery and shared CI/deployment use this app's `service.json`.

Set optional `WORKSPACE_VIEWER_URL` to the viewer's exact HTTPS origin to permit embedding through CSP `frame-ancestors`. Blank permits self framing only. Vite permits the local viewer on port 5175. Unlock remains local to this client, whether opened directly or embedded.

See [workspace architecture](../../docs/client-workspace.md) for the two-app boundary and full setup. No deployment or live provider credentials are configured by this change.
