# ShopOps standalone clients

The [system architecture](system-architecture.md) and [data/MCP design](data-and-mcp.md) define the confirmed target. This guide describes the existing foundation; its shared-workspace access does not implement the target per-user isolation.

ShopOps has two independently built and deployed client apps. Open them directly, or open the presentation-only workspace viewer to display both in one browser tab: the browser app on the left and the Telegram-style chat app in a phone-sized frame on the right. The viewer loads full documents from their separate origins; it does not import their components or hold application state, credentials, or business logic. The chat client is a standalone mobile web app, not the Telegram Bot API.

The viewer stays within one dynamic viewport with no parent scrolling. Desktop shows both apps; at 900px and below, a Browser/Chat selector changes visibility without remounting either client. Browser tabs keep independent history and drafts. Chat keeps its composer available while messages scroll, and incoming replies respect the reader's scroll position.

The chat follows Telegram conversation conventions with a compact contact header, incoming/outgoing bubbles, day separators, and a persistent Message composer. Enter sends; Shift+Enter adds a line. The Chat menu contains Load conversation and Lock. Stop and explicit history recovery remain beside the composer. ShopOps colors and identity apply throughout; no unsupported attachment, voice, presence, or read-receipt controls are shown.

For new features, follow [client development patterns](feature-development.md) and the [backend integration pattern](service-integration-pattern.md). The [browser regression suite](../tests/workspace/README.md) exercises the separate apps and APIs together.

## Services

| Service | Responsibility | Container port | Local port |
| --- | --- | --- | --- |
| shopops-web | Browser client and shop operations UI | 80 | 5173 |
| shopops-chat | Telegram-style mobile chat UI | 80 | 5174 |
| shopops-workspace | Presentation-only viewer for both client documents | 80 | 5175 |
| shopops-api | Operations persistence and browser navigation mailbox | 8000 | 8000 |
| shopops-chat-api | Conversation persistence and OpenAI Agents API streaming | 8000 | 8001 |

Each client holds its own workspace token in memory and unlocks independently, including inside the viewer. Frontend requests stay same-origin through that client's nginx/Vite proxies. The browser frontend talks only to operations. The chat frontend talks to the chat backend for messages and to the operations backend solely to publish link-navigation requests. The viewer has no API proxy and receives no tokens. Its reload controls reload one client document without resetting the other.

## Product inspection

The browser's **Products** destination opens a Shopee-inspired product gallery and detail view.
`/shop/products?shop_key=...&sku=...` selects an exact shop/SKU, including when received through
the navigation mailbox. Shop selection, product search, reviews, related orders and related returns
remain inside the independent browser app. Image URLs are optional; missing or rejected images
show a placeholder. Displayed sale prices are historical observations, not current listing prices.
A return on a related order does not establish that the selected SKU was returned.
When a browser document opens an explicit `/shop/...` URL, its first successful mailbox read
establishes a baseline instead of replacing that entry with an older stored target. Later navigation
events still open in the active tab. The ordinary app entry continues to receive the latest target.

The browser reads authenticated catalog endpoints in `shopops-api`, which calls the private
`cronjob-server` source facade over HTTP. Catalog responses use a coherent source revision and
show fetch time separately from stock observation time. Visible active product views refresh every
two seconds; hidden tabs pause and refresh when resumed. A failed refresh keeps prior records with
an explicit warning. Preparing an investigation question only creates a per-tab draft for the
separate chat; it sends no message and grants no shop-write permission.

Catalog integration defaults to disabled. The [operations API setup](../services/shopops-api/README.md)
owns its required source URL and server-side workspace identity mapping. That mapping is for the
existing single workspace; it does not implement registered-user identity or per-user vaults.
The [agent integration checklist](agent-integration.md) owns that separate integration boundary.

## Links between apps

When a user clicks a chat link, the chat client posts the safe URL to `POST /api/operations/navigation`. The operations service persists the latest navigation with a monotonically increasing identifier. The browser client polls the authenticated mailbox once per second and opens a new navigation event in its own browser view. This works for independently opened windows without sharing JavaScript state, tokens in URLs, or relying on `window.opener`. Each window must be unlocked for the same workspace. This development access model supports one workspace; targeted multi-user navigation requires scoped identity.

Local URLs such as `/shop/overview` and `/shop/incidents` resolve in the browser app's origin. Absolute HTTP(S) destinations use a sandboxed preview. The server does not fetch or proxy arbitrary destinations. Some websites prohibit embedding; the address and Open in new tab remain available. External previews receive no ShopOps bearer token or referrer; destination cookies follow the browser's own policy.

## Agent connection

The chat server targets a saved OpenAI orchestrator configured through `OPENAI_ORCHESTRATOR_AGENT_ID`; turns continue the server-owned session. `OPENAI_API_KEY` remains on the chat server. The integration uses the documented [Agents API](https://developers.openai.com/api/docs/guides/agents-api/overview). Configure the saved agent's ShopOps instructions and links to local shop routes. Agent text does not automatically execute shop mutations.

Rich replies render Markdown tables, lists, quotes, code blocks, and HTTP(S) links. Raw HTML is not executed. Interrupted or rejected provider turns remain explicit; a disconnected stream is not presented as a completed reply. Tests inject provider events and do not prove live account access.

## Development and deployment

Start operations on 8000, chat API on 8001, browser frontend on 5173, mobile chat frontend on 5174, and the optional viewer on 5175. Open the viewer for one-tab presentation, or use either direct client URL. Each service README owns its commands and runtime configuration.

For development CapRover apps:

- Browser frontend: `API_URL=http://srv-captain--shopops-api-dev:8000`.
- Mobile chat frontend: `API_URL=http://srv-captain--shopops-api-dev:8000` and `SHOPOPS_CHAT_API_URL=http://srv-captain--shopops-chat-api-dev:8000`.
- Both backends: configure `SHOP_API_TOKEN` with the same workspace secret; configure the chat backend's OpenAI key and saved agent ID separately.
- Viewer: `BROWSER_APP_URL=https://shopops-web-dev.cr.ngochoanielts.com` and `CHAT_APP_URL=https://shopops-chat-dev.cr.ngochoanielts.com`. These are public client origins, not backend upstreams.
- Both client frontends: `WORKSPACE_VIEWER_URL=https://shopops-workspace-dev.cr.ngochoanielts.com` allows that exact viewer origin to embed them through CSP `frame-ancestors`. With the variable blank, deployed clients allow only self framing. Vite permits the deterministic local viewer on port 5175.

Keep backend apps internal with no public domains or port mapping. Set backend container HTTP ports to 8000 and frontend ports to 80. Enable HTTPS for both public frontends. Leave `VITE_API_BASE_URL` unset. The chat proxy disables buffering/compression for streaming.

The viewer's `frame-src` is restricted to the configured client origins. Verify deployed CSP headers and avoid conflicting `X-Frame-Options`. External sites displayed inside the browser app may inspect the complete frame ancestor chain and refuse embedding; Open in new tab remains the fallback. These are independent web applications, not native emulators or separate browser profiles.

Give each backend its own persistent writable volume, owned by container UID 1001. Ephemeral storage is lost on replacement. Run one instance of each SQLite-backed backend; scaling requires a database/concurrency design change. Never place provider keys in Vite variables, browser storage, or URLs.

Shop-platform ingestion, production identity, multi-tenant access, and deployment credentials remain separate integrations. Live chat requires an OpenAI project with Agents API access and a provisioned saved orchestrator.

## Initial dev deployment setup

The services are prepared for dev-only deployment. Their images are `ghcr.io/swe-squad/<service>`. Create the CapRover apps `shopops-web-dev`, `shopops-chat-dev`, `shopops-workspace-dev`, `shopops-api-dev`, and `shopops-chat-api-dev`, enable each app token, and configure the runtime variables and backend volumes above. The first three are public HTTPS apps; the last two are internal apps.

For each service, run the setup command yourself with its own CapRover app token; substitute the service name and do not paste the token into chat:

```sh
CAPROVER_SERVER=https://captain.cr.ngochoanielts.com \
APP_NAME_DEVELOP=<service>-dev CAPROVER_TOKEN_DEVELOP=... \
scripts/setup-service.sh <service> dev
```

This writes the shared GitHub `codex-sea-dev` environment secrets for the service. No credentials or deployment have been configured in this implementation. A production merge will fail deployment until the corresponding production apps and secrets are provisioned. Runtime OpenAI/workspace credentials belong in CapRover App Configs, separately from deployment tokens.
