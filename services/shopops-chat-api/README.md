# ShopOps Chat API

Independent single-workspace chat backend for the configured saved orchestrator in the [OpenAI Agents API](https://developers.openai.com/api/docs/guides/agents-api/quickstart). Operations and incident storage belong to [shopops-api](../shopops-api/README.md). Provider keys never reach the browser.

Required runtime credentials: `SHOP_API_TOKEN` (workspace bearer secret), `OPENAI_API_KEY` (Agents API access), and `OPENAI_ORCHESTRATOR_AGENT_ID` (saved orchestrator reference). `CHAT_DATA_PATH` sets the SQLite path and defaults to `/data/chat.sqlite3`. Blank credentials and blank configured database paths fail startup. Supply real credentials through the runtime environment; `.env.example` documents variable names and contains no usable credentials. This service does not automatically load `.env` files.

Run `make install`, export the variables, then `make run` (local port 8001). The container listens on `PORT=8000`. Attach persistent writable storage at `/data`, owned by UID 1001. Keep the API internal and expose HTTPS through the frontend. Use the same `SHOP_API_TOKEN` in both API services for this single workspace. Run `make ci` for pinned dependency installation, Ruff, and injected-provider tests. Tests make no paid API calls.

`GET /health` is public. Other routes require `Authorization: Bearer <SHOP_API_TOKEN>`:

- `GET /api/chat/messages`: latest 100 messages in chronological order, each `{id,text,role,created_at}`. Roles are `user` or `assistant`.
- `POST /api/chat/messages` with `{text}`: a server-sent event stream. Text must contain a non-whitespace character and be at most 2000 characters. Frames contain JSON `{type:"delta",text}`, `{type:"done",message}`, or `{type:"error",message}`. Deltas append provisional text; the done message replaces it with the authoritative final reply. HTTP 401/422 reject authentication/input errors; 409 means another turn or an unresolved prior submission; 502 means saved provider state could not be inspected.

The first submission creates a saved-agent session with `environment.type="none"` and streams its initial turn. The session ID is persisted on `agent.session.created`. Follow-ups reuse that session, open `GET .../events?stream=true` before posting input, and persist a distinct idempotency key per submission. Only root-agent output is displayed. Final text parts replace provisional parts; subagent terminal events, idle events, and EOF do not imply success. See the official [events and recovery guide](https://developers.openai.com/api/docs/guides/agents-api/sessions/events).

SQLite transactions and a renewable 90-second lease serialize turns across workers sharing the same database. User input is persisted before provider I/O. Immediately before an input-bearing POST, the coordinator durably records that its outcome may become uncertain. Only a completed root turn with text creates an assistant history entry. Disconnects close the stream; bounded upstream cancellation requires confirmed input acceptance and a known session. The unfinished turn stays recoverable; history refresh or the next submission inspects its saved turn and paginated items without resending the original input. A process crash can require up to 90 seconds before another worker reclaims its lease.

Malformed saved-provider JSON, history pages, turns, or message text preserve the pending submission and release its lease. History still returns already persisted messages; a new submission returns a sanitized 502 without duplicating input. Preflight and event-stream GET failures happen before input dispatch and never trigger cancellation; history refresh releases such undispatched work locally. An input POST timeout, 5xx, or redirect retains the uncertain submission without resending or cancelling it. Only a 2xx response establishes input acceptance; explicit rejection marks the submission failed so corrected input can proceed.

If a create request loses its connection before the session ID arrives, the remote outcome cannot be located safely. The pending submission blocks new input instead of creating a duplicate session. An administrator must reconcile that session against OpenAI logs before marking the pending database row failed and setting the correct workspace session ID. Preserve a database backup before manual recovery. Explicit rejected input (for example HTTP 401 or 429) is marked failed so a corrected new submission can proceed. Failed saved sessions and required actions needing custom function results, environment access, or interactive approvals require administrator intervention; this text chat does not fabricate those results.

Credentials/account access and the saved orchestrator's real tools require a separate live smoke test. Transport contract tests verify local behavior; they do not establish provider entitlement, actual agent configuration, or tool success.

`/openapi.json` and `/docs` on this internal service declare Bearer authentication, JSON errors, and the `text/event-stream` event union. See the [service integration pattern](../../docs/service-integration-pattern.md) for adapter ownership, timeouts, navigation boundaries, and extension checks.

## Agent Core chat adapter (T09)

Select `CHAT_BACKEND=agent_core`, `CHAT_AUTH_MODE=demo_phone`, `APP_ENV=local` (or `test`).
Set `AGENT_CORE_URL`, `AGENT_CORE_SHOP_ID=shop-a`, `AGENT_CORE_CONFIG_REVISION` and
`SHOPOPS_API_URL`; all are validated before startup. Core mode requires no `OPENAI_API_KEY`
or `OPENAI_ORCHESTRATOR_AGENT_ID` in this service and makes no provider calls.
`SHOP_API_TOKEN` is used only server-side for the existing operations navigation mailbox.
If absent, navigation returns503; it is never replaced by the browser's demo session.

Exactly one public synthetic demo number, `+15550000001`, maps to existing Core fixture
`local-alice` / `tenant-a` / `alice`, restricted here to `shop-a`. Existing Core fixtures and
permissions are unchanged. This is labelled demo login without OTP; it does not verify phone
ownership. Unknown numbers do not register users or shops. Demo auth is refused outside
local/test. Tokens are random, expire after one hour, are stored only as hashes, and are kept
only in browser memory. Lock revokes the session; reload requires login again.

First successful login idempotently provisions/retrieves the shop's logical orchestrator and
persists its ID before issuing a session. Login alone creates no OpenAI session or run. First
message idempotently creates/reuses the conversation; Core owns provider execution/history.
The operator must activate the intended immutable hosted registry revision in Core separately;
selecting an adapter setting does not activate it. Existing conversations retain their revision.

Browser routes: public `GET /api/chat/auth/config`, `POST /api/chat/auth/demo-phone`;
authenticated logout, messages/history, capabilities, navigation and artifact content under
`/api/chat/`. The additive message input accepts `client_message_id` and `output_mode=text|report`.
OpenAPI documents optional assistant kind, sources and bounded report metadata. Legacy mode
returns false capabilities and rejects report requests before provider I/O.

The SQLite outbox saves exact message/mode and stable idempotency keys before HTTP submission.
Lost receipts are recovered only by replaying identical application requests with the same key.
Completed replays inspect canonical Core history; they never generate another input. Stop/disconnect
stops viewing and polling, not the remote agent. Load history explicitly to reconcile a pending
run before sending again. EOF, timeout, failed/cancelled and reconciling never produce `done`.
HTTP timeout10s, total stream budget260s, poll backoff0.5–2s and SSE comments every10s bound waiting.
History sync is bounded to100pages/30s and preserves the prior display on failure.

Reports use authenticated Blob downloads, never links containing tokens or operations navigation.
Only locally mapped artifacts in the current owner/shop/conversation namespace can be downloaded;
content is capped at1MiB and checked against metadata size/hash/media. A410 keeps history intact.

Keep `CHAT_DATA_PATH` on its own persistent volume, separate from Core's SQLite volume. Existing
legacy tables/history/session IDs are preserved. Backend/base URL/owner/shop/revision changes use
separate correlations; unresolved previous work blocks cutover. To roll back, reconcile pending
Core work first, then restore `openai_agents`/`workspace_token` and its provider settings; do not
copy Core's database or adopt old provider IDs. One Core replica/worker owns its DB.

Local ports: operations8000, chat API8001, Core8002, frontend5174. Containers retain port8000.
In CapRover, set `AGENT_CORE_URL=http://srv-captain--<core-app>:8000` and
`SHOPOPS_API_URL=http://srv-captain--<operations-app>:8000` at runtime; never use public service
domains or a hardcoded development app. Browser requests stay same-origin `/api/chat/...`;
leave `VITE_API_BASE_URL` unset. The independently hosted browser/viewer stays unchanged.

Offline loopback acceptance requires the sibling Core service's private Python3.14 environment:
run `make install` there, then explicitly run `AGENT_CORE_LOOPBACK=1 .venv/bin/pytest tests/test_agent_core_integration.py -v` here. Independent `make ci` skips this cross-service acceptance; it never silently requires another service's private environment. Its test fixture starts a real Core
application/worker with independent SQLite and an explicit fake provider; no external calls or
hosted-execution proof are implied. Paid hosted acceptance remains UNVERIFIED until both live
opt-ins, operator configuration and the two outstanding T08 proof gates are explicitly accepted.
