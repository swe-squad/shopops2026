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
- Keep the mobile frame around 390px wide where space permits and stack clients on narrow screens without unmounting them. Every frame needs a visible standalone fallback link and an accessible title.
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
