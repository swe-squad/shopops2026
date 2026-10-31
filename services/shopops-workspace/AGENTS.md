# shopops-workspace

React + TypeScript SPA built with Vite, served by nginx (`nginx.conf`, SPA fallback, `/health`).

## Commands

- Install: `npm ci`
- Dev: `npm run dev`
- Test: `npm test` (vitest + Testing Library)
- Lint: `npm run lint` (oxlint)
- Build: `npm run build`

## Conventions

- This is a presentation-only viewer. Import no code from the standalone client services and add no business APIs, access tokens, app state synchronization, or client credentials here.
- Read public runtime config from own-origin `/client-config.json`. `BROWSER_APP_URL` and `CHAT_APP_URL` must be validated origin-only values before nginx interpolation; no VITE build args.
- Mount exactly two trusted cross-origin documents. Both origins must differ from each other and the viewer; preserve the iframe sandbox, no-referrer policy, restricted CSP frame-src, and separate reload state.
- Dev/preview run on port 5175 with strictPort. Local browser origin is http://127.0.0.1:5173 and chat origin is http://localhost:5174.
- Keep the parent at one dynamic viewport with no scrolling. At widths up to 900px, switch visible clients without unmounting or removing their layout. Use overlapping grid cells and visibility/pointer-events for the inactive panel; retain its viewport dimensions while excluding it from paint, pointer and keyboard interaction. Keep the mobile frame around 390px wide where space permits. Every frame needs a visible standalone fallback link and an accessible title.
- Function components and hooks only; no class components.
- Tests query by role/label (`getByRole`), not by CSS class or test id when avoidable.

## UI design direction

The accepted [ShopOps brand](../../docs/brand/design-guidelines.md) supersedes the
historical DESIGN-notion.md template. Use canonical ivory, ink and restrained orange;
normal-size action text/buttons use action orange for contrast. Load vendored static
assets from public/brand, synced with `node scripts/sync-brand-assets.mjs` at repo root.
Keep independent build boundaries; no cross-service component imports.

Maintain a compact viewer header, fixed parent grid and child-only scrolling. Preserve
min-height/min-width zero through the frame chain. Keep accessible names, visible focus,
44px controls and reduced-motion rules. See [feature patterns](../../docs/feature-development.md)
and the [browser regression suite](../../tests/workspace/README.md).

## Review guidelines (React)

- Secrets in `VITE_*` vars or source: everything there ships to the browser.
- `useEffect` with missing/incorrect dependencies, fetches without cleanup/abort.
- `dangerouslySetInnerHTML` or unescaped user content.
- Large new dependencies that noticeably grow the bundle.
