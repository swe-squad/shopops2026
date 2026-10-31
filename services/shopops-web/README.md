# ShopOps browser app

This is the standalone browser/operations client. The separate `shopops-chat` mobile app runs in its own window and deployment. No chat client is mounted here.

The app displays the shop interface and can preview external HTTP(S) URLs in a sandbox. Some websites refuse embedding; Open in new tab is always available. Internal shop interactions call `shopops-api`. The app polls that service's authenticated navigation mailbox to open links clicked in the separate chat app. Both apps must be unlocked for the same workspace. Tokens stay in each app's memory and clear on lock/reload.

## Browser workspace

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

## Brand

Follow the canonical [ShopOps design guidelines](../../docs/brand/design-guidelines.md) and
[brand direction](../../docs/brand/brand-direction.md). Warm ivory, charcoal, the ShopOps mark, and
accessible action orange replace the original Notion/blue template. `index.html` loads the vendored
tokens and icons from `public/brand/`; the app stays independently buildable.

After changing canonical assets, run `node scripts/sync-brand-assets.mjs` at the repository root.
Validate the generated copies with `node scripts/sync-brand-assets.mjs --check`.

## Local

Run `shopops-api` on port 8000, then `npm ci` and `npm run dev -- --port 5173 --strictPort` here. Open the separate chat app on port 5174 beside this window. Run `make ci` for lint/tests/build.

## Deploy

Container port 80. Set `API_URL=http://srv-captain--shopops-api-dev:8000` (production uses `shopops-api`). Startup fails without it. Keep the backend internal and enable HTTPS on this frontend. Leave `VITE_API_BASE_URL` unset.

To display this standalone app inside the optional `shopops-workspace` viewer, set `WORKSPACE_VIEWER_URL` to that viewer's exact HTTPS origin. Blank permits self framing only. The viewer loads this app as an independent document; tokens and business state remain here. Vite permits the local viewer on port 5175.

See [standalone client architecture](../../docs/client-workspace.md) and the API README for persistent volume requirements.
