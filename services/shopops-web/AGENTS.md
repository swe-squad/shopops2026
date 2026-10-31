# shopops-web

React + TypeScript SPA built with Vite, served by nginx (`nginx.conf`, SPA fallback, `/health`).
`mock/runtime.ts` runs a Node HTTP mock alongside nginx in the same container;
`mock/connectors.ts` also serves local Vite requests. Connector state is two public
demo flags in process RAM, shared across browsers and reset on restart, with no
database or browser persistence. Do not use these flags to authorize operations.

## Commands

- Install: `npm ci`
- Dev: `npm run dev`
- Test: `npm test` (vitest + Testing Library)
- Lint: `npm run lint` (oxlint)
- Build: `npm run build`

## Conventions

- The frontend proxies `/api/` to `shopops-api` using runtime `API_URL`; see README for local and CapRover setup.
- `/api/mock/` is the explicit exception: nginx proxies it to the same container's
  loopback Node process without credentials. Keep runtime/handler tests in `mock/`;
  preserve nginx startup validation, port 80, and shutdown/failure propagation.
- Function components and hooks only; no class components.
- Tests query by role/label (`getByRole`), not by CSS class or test id when avoidable.

## UI design direction (ShopOps)

Read the canonical [design guidelines](../../docs/brand/design-guidelines.md) and
[brand direction](../../docs/brand/brand-direction.md) before changing the UI. The selected
direction is **Clarity in the chaos**. `DESIGN-notion.md` is a historical template reference;
its palette and typography are not the current product standard.

- Use canonical `--shopops-*` tokens from `public/brand/brand-tokens.css`: warm ivory canvas,
  white surfaces, charcoal text, restrained orange accents, and Inter/system typography.
  Use action orange for normal-size button text contrast; brand orange is for marks and accents.
- Vendor assets through `node scripts/sync-brand-assets.mjs` from the repository root.
  Run `node scripts/sync-brand-assets.mjs --check` to detect drift. Edit the canonical brand kit,
  not the generated copies in `public/brand/`.
- Keep the document and browser chrome inside the viewport. `.shop-page` owns vertical shop
  scrolling; the tab strip owns horizontal overflow. Do not introduce page-level scrolling.
- Prioritize interaction space: use a compact app header and a single shop navigation row.
  Keep decorative titles and explanatory copy out of extra chrome rows; retain 44px controls.
- Keep inactive tab panels mounted. History, address drafts, incident drafts, local scroll,
  and external previews belong to each tab. New chat navigation targets the active tab.
- Preserve accessible tab semantics, visible keyboard focus, ArrowLeft/ArrowRight/Home/End
  selection, Delete to close, and 44px touch targets. Closing the last tab opens a fresh overview.
- Show loading, empty, error, retry, saving, and success states without inventing connected shop
  data. Errors and statuses need text or icons as well as color. Respect reduced motion.
- Check desktop, phone, tablet, and short landscape sizes. Keep wide content inside its owner.
- Keep this client independent from `shopops-chat` and `shopops-workspace`: separate documents,
  state, tokens, and builds. Shared assets do not authorize shared application code or credentials.

## Review guidelines (React)

- Secrets in `VITE_*` vars or source: everything there ships to the browser.
- `useEffect` with missing/incorrect dependencies, fetches without cleanup/abort.
- `dangerouslySetInnerHTML` or unescaped user content.
- Large new dependencies that noticeably grow the bundle.
