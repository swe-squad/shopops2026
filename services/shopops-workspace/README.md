# ShopOps workspace viewer

A presentation-only page that displays the independently hosted shop browser and Telegram-style chat apps in one tab. The viewer owns their layout and individual reload/open controls. It imports no client app code, handles no workspace tokens, and calls no business API. Each child remains a standalone application with its own session, build, and backend.

## Local development

Start the two standalone apps first:

- Shop browser: `http://127.0.0.1:5173`
- Agent chat: `http://localhost:5174`

Run `npm ci` and `npm run dev` here, then open `http://localhost:5175`. The viewer uses strict port 5175. Vite serves public `/client-config.json` with the two origins above and limits its frame sources to those origins. `npm run preview` serves the same local config after a build. The child apps must allow the viewer's origin in their embedding policy; see [workspace architecture](../../docs/client-workspace.md).

Unlock each app inside its own frame. Chat links use the existing operations navigation endpoint to update the browser app. The viewer does not read or relay their data. Reload browser app resets only that child; reload chat app resets only chat. Open in new tab is always available when embedding is unavailable. On narrow screens the clients stack, with no frame remount caused by layout changes.

## Runtime configuration and CapRover

This service listens on container port **80** and has no API proxy or frontend build arguments. Set both public client origins in CapRover App Configs:

- `BROWSER_APP_URL=https://shopops-web-dev.cr.ngochoanielts.com`
- `CHAT_APP_URL=https://shopops-chat-dev.cr.ngochoanielts.com`

Use the corresponding service app names without `-dev` in production. Both must be origins only: scheme, hostname, and optional port. Paths, trailing slash, query, fragment, credentials, whitespace, and quotes are rejected. HTTPS is required except for HTTP `localhost` or `127.0.0.1` during local development. Hostname/IPv4 origins are supported; IPv6 origin syntax is not supported by the runtime validator. Port must be 1–65535.

`require-env.sh` runs before nginx's environment substitution. It validates the entire values before they enter JSON or the CSP header, rejects equivalent client origins, and fails startup if either variable is absent. The browser validates the public config again and refuses to mount clients on the same origin as each other or the viewer. Invalid config displays a retry action with no frames mounted.

nginx serves `/client-config.json` from these runtime values and sets `frame-src` to exactly the configured origins. The outer frames permit scripts, same-origin behavior, forms, and popups for these trusted cross-origin apps; top navigation stays unavailable. Referrers are suppressed. Each client also needs a matching `frame-ancestors` policy to allow this viewer. No secrets belong in this service's environment or client configuration.

## Validation

`make ci` installs the lockfile and runs lint, tests, and the production build. Tests cover config/URL rejection, independent frame reload identity, config retry and abort, and shell interpolation defenses including multiline values, quotes, invalid hosts, and invalid ports. Browser inspection and the cross-app navigation flow are coordinated from the parent workspace task.
