# ShopOps browser app

This is the standalone browser/operations client. The separate `shopops-chat` mobile app runs in its own window and deployment. No chat client is mounted here.

The app displays the shop interface and can preview external HTTP(S) URLs in a sandbox. Some websites refuse embedding; Open in new tab is always available. Internal shop interactions call `shopops-api`. The app polls that service's authenticated navigation mailbox to open links clicked in the separate chat app. Both apps must be unlocked for the same workspace. Tokens stay in each app's memory and clear on lock/reload.

## Landing and login

`/` is the public English landing page. Its login links open `/login` in the
same app. The login form checks the workspace token with an uncached read of
`/api/operations/incidents` before opening the workspace. Invalid tokens stay on
the form with an error; network/server failures allow retry. Leaving the form
cancels validation. This remains shared workspace-token access, not account
registration or per-user authentication.

Successful login opens `/shop/connections`. Visiting a `/shop/...` deep link first
returns to that path after login, including its query and fragment. The `next`
parameter accepts only local shop paths; unsafe or unrelated destinations fall
back to Connections. Other application paths show a not-found page.

Tokens stay in React memory. Reloading a protected route requires login again;
**Lock workspace** clears the token and returns to `/login`. The brand link opens
the landing page without reloading the document, so its workspace CTA can return
using the current session. Leaving the workspace discards its tabs; switching
between tabs inside the workspace preserves them as before. Chat remains an
independent login. No token is stored in browser storage, URLs, or mock requests.

Landing/login scroll inside their own content area, keeping the document and
embedding viewer within the viewport. The landing describes actual manual
operations and explicitly labels marketplace connections as a simulation.

## Browser workspace

Logging in from the landing page opens **Connections**. Choose **Log in to Shopee** or
**Log in to TikTok** to exercise the mock connection flow, then return from the
success page to see **Connected**. Existing `/shop/...` deep links keep their target;
new internal tabs still open Overview. The initial chat navigation mailbox snapshot
establishes a baseline without replaying an old link over the login destination;
new events after that initial sync still open in the active tab. Connections is also in the shop navigation.

The mock API lives in this service, with two flags in one Node process's RAM:

| Endpoint | Result |
| --- | --- |
| `GET /api/mock/connectors` | `{connections: [{platform, connected, mock: true}, ...]}` for Shopee and TikTok |
| `PUT /api/mock/connectors/shopee` or `/tiktok` | No body; idempotently set that flag and return `{platform, connected: true, mock: true}` |

These public demo flags are shared by every browser using this service instance.
They survive browser refresh, closing a browser, and locking/unlocking the UI.
Restarting the mock process/container or redeploying resets both flags. Run one
replica for a consistent demo; replicas do not share RAM. No database, browser
storage, account identity, or real platform credentials are involved. The mock
does not authenticate users or grant access to operations data. It never contacts
Shopee/TikTok, imports records, or changes the manual-incidents behavior.

Responses are uncached. Invalid platforms return 400, unknown paths 404, unsupported
methods 405, and cross-origin mutations 403. The UI checks the API on entry,
reload, and unlock; it shows checking/saving/errors and only opens success after
a successful write. Reopen Connections or use **Reload page** to see changes from
another browser. Requests carry no workspace token or cookies.

Use **New browser tab** to open another overview. Each tab retains its own back/forward history,
address draft, incident form, content scroll, and external iframe while switching. Selecting a tab
does not reload it. New navigation events from chat open in the active tab; repeated mailbox events
are ignored. **Reload page** refreshes the selected tab's data or external preview. Closing the last
tab opens a fresh overview.

The tab strip supports Left/Right arrows (including wraparound), Home, End, and Delete to close.
The document and browser controls stay within one viewport; shop content scrolls in `.shop-page`
and a long tab strip scrolls horizontally. On small screens, the same controls remain available.

The current access model is one workspace, and incidents are manually entered until shop ingestion
is connected. Each tab loads its own incident view; use **Refresh** to see records added elsewhere.
Failed saves keep the form draft. Closing a tab or locking cancels its pending requests; a write
already accepted by the server may still complete, so refresh records before retrying it.
Incident timestamps without an offset are treated as UTC, matching the API's SQLite storage;
the browser displays them in the seller's local timezone.

## Product inspection

Open **Products** to browse the authenticated catalog from the persistent mock shop source.
Choose a shop, search by product name or SKU, and open a product to inspect reviews, related
order lines, and returns on those orders. A related return does not establish which SKU was
returned. Catalog availability is configured in [shopops-api](../shopops-api/README.md);
a disconnected source shows an error and Retry without generated catalog data.

Product links use `/shop/products?shop_key=<encoded>&sku=<encoded>`; omit `sku` for the gallery.
The current browser tab owns its selection, history, search, and product question drafts.
The selected visible product view refreshes about every two seconds, pauses in inactive tabs
or a hidden document, and preserves the last good records with a stale notice after errors.
Source revision and fetch time identify the snapshot. Stock is an observation; the displayed
sale price is the last observed sale, not a current listing price. Unknown values remain unknown.

Source-provided HTTPS product images appear when available. Missing, unsafe, or broken image
URLs show a labeled placeholder. **Prepare question draft** creates an editable question scoped
to the selected shop and SKU; copy it into the independent chat client yourself. It does not
send a message or perform a shop action. Drafts clear when the tab closes or the workspace locks.

## Brand

Follow the canonical [ShopOps design guidelines](../../docs/brand/design-guidelines.md) and
[brand direction](../../docs/brand/brand-direction.md). Warm ivory, charcoal, the ShopOps mark, and
accessible action orange replace the original Notion/blue template. `index.html` loads the vendored
tokens and icons from `public/brand/`; the app stays independently buildable.
Products adds a commerce-orange header, neutral gray canvas, and white image tiles while retaining
the ShopOps identity and accessible action colors.

After changing canonical assets, run `node scripts/sync-brand-assets.mjs` at the repository root.
Validate the generated copies with `node scripts/sync-brand-assets.mjs --check`.

## Local

Run `shopops-api` on port 8000, then `npm ci` and `npm run dev -- --port 5173 --strictPort` here. Open the separate chat app on port 5174 beside this window. Run `make ci` for lint/tests/build.

Vite mounts the same mock handler as the container. Restarting the dev server
resets its RAM flags. Tests include real HTTP calls and supervised-process lifecycle
checks; the workspace Playwright suite also covers mock connection/relogin flows.

## Deploy

Container port 80. Set `API_URL=http://srv-captain--shopops-api-dev:8000` (production uses `shopops-api`). Startup fails without it. Keep the backend internal and enable HTTPS on this frontend. Leave `VITE_API_BASE_URL` unset.

The image adds Node 24 alongside nginx. The Node entrypoint binds the mock server
to `127.0.0.1:3001` and starts the standard nginx entrypoint; nginx exposes
`/api/mock/` on port 80 and strips Authorization/Cookie headers before forwarding.
CapRover's forwarded HTTPS scheme is retained for same-origin checks. The existing
`/api/operations/` proxy, static assets, SPA fallback, viewer CSP and `/health`
remain in nginx. No new runtime variables or volumes are needed. If nginx exits
or the mock listener fails, the supervising process exits; SIGTERM stops both.
Use `make docker` to build the image. Reverting the feature image needs no migration.

To display this standalone app inside the optional `shopops-workspace` viewer, set `WORKSPACE_VIEWER_URL` to that viewer's exact HTTPS origin. Blank permits self framing only. The viewer loads this app as an independent document; tokens and business state remain here. Vite permits the local viewer on port 5175.

See [standalone client architecture](../../docs/client-workspace.md) and the API README for persistent volume requirements.
