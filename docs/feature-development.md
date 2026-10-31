# Extending the independent ShopOps clients

The [system architecture](system-architecture.md) and [data/MCP design](data-and-mcp.md) define the confirmed target. This guide describes the existing foundation; its shared-workspace access does not implement the target per-user isolation.

Read [client setup](client-workspace.md), [brand guidelines](brand/design-guidelines.md), and the owning service's `AGENTS.md`. Browser, Telegram-style chat and viewer remain three separate apps. Integrate through API contracts; never import application code from another service.

## Choose the owner

| Work | Owner | Boundary |
| --- | --- | --- |
| Frame layout, visible-client switch, reload/open controls | `shopops-workspace` | Public origins only; no business API, credentials or app state |
| Browser tabs, shop routes, forms and evidence views | `shopops-web` | Operations API; tab state belongs here |
| Conversation, composer, rich replies and links | `shopops-chat` | Chat API plus navigation POST to operations |
| Shop data, durable business actions, navigation mailbox | `shopops-api` | Typed contracts, authorization, its own SQLite |
| Orchestrator sessions, streaming, recovery | `shopops-chat-api` | Provider credentials and session lifecycle stay server-side |
| Visual identity | `docs/brand/assets` | Canonical tokens/assets vendored into each frontend |

The [backend integration pattern](service-integration-pattern.md) describes adapter boundaries, validation and future service calls. Add a service only for a real deployable boundary. Do not place integration logic in the viewer or provider credentials in a browser bundle.

## Preserve the viewport contract

The viewer is a `100dvh` grid with `auto minmax(0, 1fr)` rows. Content-bearing grid/flex descendants and iframes need `min-height: 0` and `min-width: 0`. The parent document never scrolls. Do not add fixed minimum frame heights, an overflowing footer, or a second client below the fold.

Desktop displays both full documents side by side. At 900px and below, CSS and the labeled Browser/Chat selector change visibility. Keep both iframe nodes mounted: view switches/resizes preserve sessions, drafts, scroll and streams. Only an explicit per-client reload replaces an iframe.

At narrow sizes the panels overlap one grid cell. Hide the inactive panel with `visibility: hidden` and `pointer-events: none`, retaining its layout. Do not use `display: none`, which collapses the inactive client's viewport. Browser tests assert retained dimensions and exclusion from keyboard navigation.

The browser fixes tab/address controls while shop content owns vertical scrolling. Selecting tabs preserves per-tab history and drafts. Chat fixes its header/composer while the conversation owns scrolling. Wide tables/code scroll horizontally inside their own containers. Incoming tokens must not drag a reader away from older messages; provide jump-to-latest.

Keep the chat experience familiar to Telegram users: a compact conversation identity, dated incoming/outgoing bubbles and a persistent message composer. Enter sends, Shift+Enter adds a line, and composing an IME character must never submit. Preserve ShopOps branding. Presence, delivery, and read states must reflect real backend evidence; do not add decorative attachment, voice, or navigation controls without working behavior.

External previews are sandboxed iframes, not full browser engines: some sites reject framing, and native cross-origin history cannot be inspected. Retain Open in new tab. Never forward a workspace bearer token to a destination.

## Implement one feature

1. Record outcome, owner, unchanged contracts and observable acceptance checks. Inspect existing modules/tests; assign disjoint files to agents.
2. Define typed requests/responses and errors in the owning API. Specify timeout, cancellation and mutation recovery before wiring the UI. Test adapters with explicit fixtures; do not ship fabricated shop records.
3. Implement in the standalone client first. Include loading, empty, error, disabled, success and keyboard/focus states. Use canonical tokens and existing controls; use action orange for normal-size text/buttons.
4. Verify standalone and embedded layouts, including short-height/phone/tablet/desktop. Keep app state and credentials out of the viewer.
5. Cover state/API behavior in service tests; cover cross-document interaction, real layout and scrolling in browser tests. Do not weaken failing assertions.
6. Run focused checks, affected service CI and the integration suite. Review the final diff and update the smallest owning docs. Deploy only within authorized environment/scope.

## Brand synchronization

Edit JSON/CSS tokens together under `docs/brand/assets/tokens`, then run from the root:

```sh
node scripts/sync-brand-assets.mjs
node scripts/sync-brand-assets.mjs --check
```

The script validates JSON/CSS equivalence and copies selected assets into each frontend's `public/brand/`. Commit copies with the canonical change. Service builds do not depend on siblings. Component/layout tokens stay local unless accepted as brand-level decisions.

## Validation and processes

Run `make ci` inside changed services and the [browser suite](../tests/workspace/README.md). The dedicated [workspace CI workflow](../.github/workflows/workspace-checks.yml) checks brand drift and browser interactions when canonical assets, test tooling or any participating service changes. The suite starts all five services with temporary databases and an offline provider fixture, fails on occupied ports and terminates owned processes. Brand changes also run the drift check above.

For manual development inspect ports 5173–5175 and 8000–8001 first. Reuse known owned processes or stop them cleanly; do not keep incrementing ports. Track command, PID, port and worktree. Stop owned processes when done, never another session's processes.

Local tests do not prove live provider access, physical mobile keyboards, container builds or deployed framing headers. Verify those separately when the relevant environment is available.
