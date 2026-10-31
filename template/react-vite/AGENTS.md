# __SERVICE_NAME__

React + TypeScript SPA built with Vite, served by nginx (`nginx.conf`, SPA fallback, `/health`).

## Commands

- Install: `npm ci`
- Dev: `npm run dev`
- Test: `npm test` (vitest + Testing Library)
- Lint: `npm run lint` (oxlint)
- Build: `npm run build`

## Conventions

- Config is baked in at build time through `VITE_*` env vars, read only in `src/config.ts`.
  New `VITE_*` vars must also be added to the `Dockerfile` ARGs, `service.json` `buildArgVars`,
  and as GitHub environment variables.
- API calls go to `/api/...` on the same origin. nginx (`nginx.conf`) proxies them to runtime env `API_URL`
  (set in CapRover App Configs, e.g. `http://srv-captain--<api>-dev:<port>`); the container refuses to start
  without it (`require-env.sh`). Locally Vite proxies `/api/` to `localhost:8080`. Keep `VITE_API_BASE_URL` empty.
- Function components and hooks only; no class components.
- Tests query by role/label (`getByRole`), not by CSS class or test id when avoidable.

## UI design direction (Notion-inspired)

Read [DESIGN-notion.md](./DESIGN-notion.md) before creating or changing UI. Use its palette,
typography, spacing, shapes and component guidance as the default unless the user specifies
another direction. Translate the design language to the service's actual workflows; marketing
examples such as pricing cards and hero bands are optional, not required app features.

- Aim for a calm, document-like workspace: generous whitespace, clear content hierarchy,
  restrained chrome and readable lists/tables. Group content through spacing before adding cards.
- Use warm paper `#f6f5f4` for the page canvas, white `#ffffff` for panels and inputs,
  near-black text, `#615d59` for supporting copy and `#e6e6e6` for 1px dividers/borders.
- Reserve blue `#0075de` for primary actions, links and active/focus indicators; use
  `#005bab` for pressed primary buttons. Keep secondary actions neutral. Sticker colours
  (purple, pink, orange, teal, green) belong in small illustrations, icon tiles and category dots.
  Error/success states must remain understandable through text or icons as well as colour.
- Use Inter when available with a system sans-serif fallback; do not depend on NotionInter.
  Keep body text at 15–16px, weight 400 and comfortable line-height (about 1.5 for prose).
  Use weight 600–700 for headings and tighter tracking for large titles. Reserve 54–64px
  display sizes for marketing heroes; keep workspace headings appropriate to the content.
- Reuse spacing tokens of 4, 8, 12, 16, 24, 28 and 32px. Use around 24px padding in cards
  and generous section gaps; keep data-heavy views compact enough to scan comfortably.
- Use 4px radii for inputs, 5px for menu/list rows, 8px for utility buttons and 12–16px
  for cards/large containers. Fully rounded pills suit marketing CTAs and badges.
  Prefer hairline borders; apply subtle shadows only where elevation helps, such as popovers.
- Keep navigation quiet, with subtle row hover states and an obvious active indicator.
  Forms need visible labels, clear validation and keyboard focus. Provide loading, empty,
  error and disabled states using the same visual system.
- Adapt grids to two columns on tablet and one on mobile where appropriate; collapse navigation
  when needed and keep mobile touch targets at least 44×44px. Contain wide tables in their own
  scroll area so the page itself does not overflow.
- Use decorative colour sparingly. Avoid heavy shadows and repeated dark sections; the deep
  indigo `#213183` hero treatment is an optional, single marketing moment.
- Define reusable CSS custom properties for the design tokens and share component styles
  rather than scattering one-off values. Check changed screens at desktop and mobile widths,
  including keyboard focus and readable text contrast; faint decorative tokens are not body text.

## Review guidelines (React)

- Secrets in `VITE_*` vars or source: everything there ships to the browser.
- `useEffect` with missing/incorrect dependencies, fetches without cleanup/abort.
- `dangerouslySetInnerHTML` or unescaped user content.
- Large new dependencies that noticeably grow the bundle.
