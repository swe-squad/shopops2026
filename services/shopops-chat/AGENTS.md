# shopops-chat

React + TypeScript SPA built with Vite, served by nginx (`nginx.conf`, SPA fallback, `/health`).

## Commands

- Install: `npm ci`
- Dev: `npm run dev`
- Test: `npm test` (vitest + Testing Library)
- Lint: `npm run lint` (oxlint)
- Build: `npm run build`

## Conventions

- This is the standalone Telegram-style mobile web app. The presentation-only workspace may embed its complete document, but do not import its components into the shop browser or share client state.
- Runtime `SHOPOPS_CHAT_API_URL` proxies `/api/chat/` to the chat API. Runtime `API_URL` proxies only `/api/operations/navigation` to the operations API. Keep provider keys server-side and `VITE_API_BASE_URL` unset.
- Dev runs on port 5174 with strictPort. Vite proxies chat to 127.0.0.1:8001 and navigation to 127.0.0.1:8000.
- Preserve `/shop/...` navigation payloads as origin-relative paths; the independently hosted browser app resolves them. Tokens remain in each app's memory and must not appear in link URLs.
- Preserve safe-area/composer behavior, stream abort cleanup, and explicit history reload after interruption. Never silently resend a chat turn.
- Function components and hooks only; no class components.
- Tests query by role/label (`getByRole`), not by CSS class or test id when avoidable.

## ShopOps brand and conversation layout

Read [brand direction](../../docs/brand/brand-direction.md) and [design guidelines](../../docs/brand/design-guidelines.md)
before changing UI. They replace the inherited `DESIGN-notion.md` template direction.

- Consume canonical tokens and mark from `public/brand/`; edit the source kit in `docs/brand/assets/`,
  then run `node scripts/sync-brand-assets.mjs` from the repo root. Verify with `--check`.
  Each client vendors only static brand assets and builds independently.
- Use ivory, white, charcoal and restrained orange. Use action orange for small text and primary
  buttons; the brighter brand orange is for marks and accents. Keep focus visible, primary controls
  at least 44×44px, and status text understandable without color.
- Preserve the Telegram-style contact conversation: compact ShopOps name/circular avatar, honest
  assistant/loading/typing state, rounded incoming/outgoing bubbles with tails, quiet bottom-right
  timestamps, local wallpaper and a pill composer with paper-plane send. No fake online/read receipts
  or decorative attachment/voice/back controls. Day separators derive from message timestamps in the
  viewer's local time; never invent a conversation date.
- `chat-actions-menu.tsx` owns real history reload and lock actions. Keep menu keyboard navigation,
  Escape focus return, outside/blur dismissal, and disabled reload while busy. Recovery stays visible
  beside the composer instead of requiring the menu.
- Keep the signed-in app in one viewport: `.chat-header` and `.composer-area` stay outside the
  conversation scroll. The single `role="log"` named `Conversation` owns message scrolling.
  Table/code regions may scroll horizontally and must remain keyboard reachable.
- `use-conversation-scroll.ts` follows incoming content only while near the bottom. Readers above
  keep their position and get an explicit Jump to latest control. Observe viewport/content resizing
  without forcing readers back to the bottom. Keep upward wheel/touch and keyboard intent handling:
  native scroll events can arrive after a streamed layout update. Never cancel native scrolling.
- `use-mobile-viewport.ts` follows the visual viewport only when standalone and unzoomed. An embedded
  client follows its iframe. Preserve dynamic-height fallback, safe-area padding and short-height layout.
- Keep Markdown in `rich-message.tsx` with raw HTML disabled, remote images rendered as text, and links
  delivered through `onNavigate`. Presentation styles live in `rich-message.css`; never load remote
  media or use `dangerouslySetInnerHTML` for messages.
- After stop or stream failure, preserve partial text and require explicit history loading before a
  new turn. Recovery stays next to the disabled composer; loading history never resends a message.
- Keep loading, empty, failure, responding and locked states truthful. No invented shop data, connection
  state or successful-action claims. Verify desktop/mobile layouts and reduced-motion behavior.

## Review guidelines (React)

- Secrets in `VITE_*` vars or source: everything there ships to the browser.
- `useEffect` with missing/incorrect dependencies, fetches without cleanup/abort.
- `dangerouslySetInnerHTML` or unescaped user content.
- Large new dependencies that noticeably grow the bundle.
