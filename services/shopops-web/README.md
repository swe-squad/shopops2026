# ShopOps browser app

This is the standalone browser/operations client. The separate `shopops-chat` mobile app runs in its own window and deployment. No chat client is mounted here.

The app displays the shop interface and can preview external HTTP(S) URLs in a sandbox. Some websites refuse embedding; Open in new tab is always available. Internal shop interactions call `shopops-api`. The app polls that service's authenticated navigation mailbox to open links clicked in the separate chat app. Both apps must be unlocked for the same workspace. Tokens stay in each app's memory and clear on lock/reload.

## Local

Run `shopops-api` on port 8000, then `npm ci` and `npm run dev -- --port 5173 --strictPort` here. Open the separate chat app on port 5174 beside this window. Run `make ci` for lint/tests/build.

## Deploy

Container port 80. Set `API_URL=http://srv-captain--shopops-api-dev:8000` (production uses `shopops-api`). Startup fails without it. Keep the backend internal and enable HTTPS on this frontend. Leave `VITE_API_BASE_URL` unset.

To display this standalone app inside the optional `shopops-workspace` viewer, set `WORKSPACE_VIEWER_URL` to that viewer's exact HTTPS origin. Blank permits self framing only. The viewer loads this app as an independent document; tokens and business state remain here. Vite permits the local viewer on port 5175.

The current access model is one workspace, and incidents are manually entered until shop ingestion is connected. See [standalone client architecture](../../docs/client-workspace.md) and the API README for persistent volume requirements.
