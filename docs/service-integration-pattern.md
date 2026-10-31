# Service integration pattern

The [system architecture](system-architecture.md) and [data/MCP design](data-and-mcp.md) define the confirmed target. This guide describes the existing foundation; its shared-workspace access does not implement the target per-user isolation.

Use this guide when adding a real ShopOps feature. [Client workspace](client-workspace.md) owns topology and deployment setup; each service README owns its commands and environment. The two backends remain independent applications with independent databases. No shop-platform ingestion, Telegram Bot API, production identity, or new external integration is connected by this foundation.

## Ownership and extension points

| Responsibility | Current owner | Where to extend |
| --- | --- | --- |
| Incident records and navigation mailbox | `shopops-api` | [Operations router](../services/shopops-api/app/operations.py), [navigation router](../services/shopops-api/app/navigation.py), [app factory](../services/shopops-api/app/main.py) |
| Conversation lifecycle and recovery | `shopops-chat-api` | [Chat coordinator](../services/shopops-chat-api/app/chat.py), [SQLite store](../services/shopops-chat-api/app/store.py) |
| OpenAI wire protocol | `shopops-chat-api` | [Provider adapter](../services/shopops-chat-api/app/provider.py), [output normalization](../services/shopops-chat-api/app/output.py) |
| Shop routes, active browser tab and incident interactions | `shopops-web` | [Browser pane](../services/shopops-web/src/browser-pane.tsx), [incident requests](../services/shopops-web/src/use-incidents.ts), [navigation polling](../services/shopops-web/src/use-navigation-requests.ts) |
| Message rendering, sending and clicked-link delivery | `shopops-chat` | [Chat controller](../services/shopops-chat/src/use-chat-controller.ts), [stream transport](../services/shopops-chat/src/workspace-api.ts), [navigation publisher](../services/shopops-chat/src/use-browser-navigation.ts) |
| Client frames, sizing, selection and individual reload | `shopops-workspace` | [Viewer](../services/shopops-workspace/src/App.tsx), [frame wrapper](../services/shopops-workspace/src/client-frame.tsx) |

The viewer receives public client origins only. Tokens, business requests, navigation destinations, provider state, and message history belong to the clients or their APIs. Do not import another service's Python modules, React components, or database files to cross this boundary.

## Request → application logic → adapter → storage

1. Define request and response Pydantic models in the owning API. Validate lengths, blank values, URL rules, and permitted values at entry. Register the route with the existing workspace authorization dependency and explicit response/error models.
2. Keep simple local CRUD in the existing operations routers. Introduce an application service only when a real workflow needs coordination. The chat coordinator is the existing example: it owns sequencing and decides when a turn is recoverable or complete.
3. Put external HTTP calls in an adapter owned by the calling backend. The adapter owns credentials, provider paths, response validation, pagination, timeouts, and sanitized errors. Inject its transport for tests. Normalize provider output into the application's contracts before sending it to a browser.
4. Keep transactions and persistence in the storage boundary. Operations routers currently use the app's transaction context; chat uses `Store` through `Chat.db`, which runs blocking SQLite work outside the async event loop. Never hold a database transaction across provider I/O.
5. Add the client request and UI state in the owning standalone app. Use same-origin `/api/...` calls with its in-memory workspace token and an `AbortSignal`. Keep loading, empty, failed, and interrupted states explicit.

No common integration framework or empty adapter is needed before a feature has a concrete upstream and contract. Future shop mutations need their own accepted approval, authorization, execution, and verification behavior; assistant text and navigation links currently execute no shop mutation.

## Existing public contracts

Each backend exposes `/openapi.json` and `/docs` on its own internal origin. OpenAPI declares `WorkspaceToken` as HTTP Bearer and leaves `/health` unauthenticated. Browser access to those internal docs is not added to the frontend proxy.

| Route | Result |
| --- | --- |
| `GET /health` on either API | `{status:"ok"}`; process health, not an external provider readiness probe |
| `GET /api/operations/incidents` | Latest 100 incidents, newest first |
| `POST /api/operations/incidents` | `{title,detail?}` → HTTP 201 persisted incident |
| `GET /api/operations/navigation` | Latest `{id,url}` or JSON `null` |
| `POST /api/operations/navigation` | `{url}` → HTTP 201 `{id,url}` |
| `GET /api/chat/messages` | Latest 100 persisted messages in chronological order |
| `POST /api/chat/messages` | `{text}` → `text/event-stream` |

Model fields and validation limits are owned by [operations](../services/shopops-api/app/operations.py), [navigation](../services/shopops-api/app/navigation.py), and [chat contracts](../services/shopops-chat-api/app/contracts.py). Error responses before a stream begins are JSON: 401 for workspace authentication, 422 for input validation, 409 for an active or uncertain previous chat turn, and 502 when saved provider state cannot be inspected safely. Keep client types and tests aligned when intentionally changing these contracts.

### Streaming and recovery

SSE uses `data: <JSON>` followed by a blank line. The emitted events share the Pydantic models advertised in OpenAPI:

- `delta` with `text`: append provisional text.
- `done` with `message`: replace provisional text with the persisted authoritative assistant message.
- `error` with `message`: show an interrupted/failed reply; HTTP status cannot change once streaming begins.

Root-orchestrator completion with text is required before saving an assistant reply. Subagent completion, idle events, EOF, and an incomplete frame do not establish success. The frontend decoder handles frame and UTF-8 boundaries split across network chunks. nginx must preserve streaming by disabling buffering and caching for chat responses.

Chat saves user input, a distinct submission key, and a database lease before provider I/O. Follow-ups open the saved session's event stream before posting input with that key. The provider adapter calls the coordinator immediately before each input-bearing POST, so uncertain-send intent is durably recorded before either a session-create request or follow-up input can leave the process. Opening a GET stream is not an input attempt. The existing `dispatched` database field records this conservative intent, not proof of acceptance; a crash between recording it and issuing the POST must still recover conservatively.

| Input boundary | Recovery and cancellation |
| --- | --- |
| Event-stream GET fails before input POST | Undispatched. History refresh or the next submission releases it locally without provider recovery or cancellation. |
| Input POST explicitly rejected | Mark failed and permit a corrected submission; do not cancel. |
| Input POST times out, returns 5xx, or redirects | Keep pending and inspect saved state before new input. Do not resend or cancel without confirmed acceptance. |
| Input POST returns 2xx | Acceptance confirmed. An interrupted stream can attempt cancellation for its known session; the pending outcome still requires recovery. |

A 90-second lease renews every 10 seconds; a crash may take up to 90 seconds to reclaim. Recovery has a 60-second deadline and only inspects saved state, never resends an uncertain input. The provider adapter has a 30-second general HTTP timeout and 120-second read timeout; cancellation after accepted input is bounded to 5 seconds. Failed preflight or stream-opening reads cannot establish cancellation ownership.

Malformed saved provider responses leave the pending turn intact and release its lease. History can still show previously persisted messages; a new submission returns a sanitized 502. An ambiguous create with no saved session ID remains blocked until an administrator reconciles it. See [chat recovery limits](../services/shopops-chat-api/README.md). Transport fixtures verify these local decisions; they do not prove live account access or real tool execution.

### Navigation ownership

Only an explicit chat-link click publishes a navigation event. The operations API stores one latest event with an increasing ID; it does not fetch the destination. The browser client polls once per second, deduplicates IDs, and applies a new destination to its active tab. Navigation is a latest-value mailbox, so rapid publications can replace an unread earlier event; it is not a durable delivery queue or a message acknowledgment system.

`/shop` and `/shop/...` stay origin-relative until the browser app resolves them. Absolute HTTP(S) links use the browser app's sandboxed preview. Unsafe schemes, embedded credentials, whitespace/control characters, backslashes, and protocol-relative URLs are rejected. Never place workspace credentials in destination URLs, the viewer configuration, iframe messages, or external requests. External sites may refuse embedding; the standalone open action remains available.

## Runtime and persistence rules

- Workspace access uses one shared `SHOP_API_TOKEN`, checked independently by each backend. Each client holds its own token in memory. This is one workspace, not user accounts, roles, or tenant isolation.
- OpenAI credentials and agent configuration belong only to the chat API. Blank credentials or blank configured database paths fail startup. Environment names and defaults are owned by the [operations example](../services/shopops-api/.env.example), [chat example](../services/shopops-chat-api/.env.example), and service READMEs.
- A future service-to-service call uses a required runtime `<CALLEE>_URL`, with hyphens replaced by underscores. Document a localhost example in the caller's `.env.example`; do not supply a development-app fallback in code. In CapRover use `http://srv-captain--<app-name>:<container-port>`, never a backend's public domain. The existing frontend upstreams are documented in [client workspace](client-workspace.md).
- Give each backend a separate writable persistent volume owned by UID 1001. Run one instance per SQLite-backed service. Chat leases protect workers sharing the same database file; they do not create a multi-replica database architecture.
- Preserve existing data and add explicit migration/rollback steps when storage changes. The current foundation adds no database schema migration. Operations preserves legacy `messages` tables without copying them into the chat database.
- Translate upstream failures into safe application errors. Never return or log provider response bodies, prompts, tool arguments, bearer credentials, or personal data. Do not automatically retry an uncertain mutation or streamed submission without proven idempotency/recovery semantics.

## Feature delivery checks

For a future feature, identify its owning service and accepted user outcome first. Update only that service's route/models, application logic, adapter/storage when needed, client behavior, and owning setup docs. Add cross-service calls only through an explicit API. Validate authentication, rejected input, persistent behavior after restart, upstream failure, cancellation, and duplicate-submission behavior where applicable.

From each affected service run `make ci`. The APIs install pinned dependencies, lint/format-check, and run pytest. Their [operations contract tests](../services/shopops-api/tests/test_contract.py), [chat contract tests](../services/shopops-chat-api/tests/test_integration_contract.py), and [recovery tests](../services/shopops-chat-api/tests/test_recovery.py) exercise real app factories and temporary SQLite databases with an injected HTTP transport.

Run the [workspace browser suite](../tests/workspace/README.md) for flows that cross the clients: it uses separate real frontend documents and APIs, with only OpenAI transport replaced by an explicit offline test fixture. Keep that fixture outside production services. Live OpenAI entitlement, saved-agent tools, CapRover routing/CSP, external embedding policies, and physical-device keyboards require their own scoped verification and are not established by offline tests.
