# Backend integration foundation

Status: DONE

Scope: `services/shopops-api/**`, `services/shopops-chat-api/**`, `docs/service-integration-pattern.md`. Worktree `/private/tmp/shopops2026-shopops-web`, branch `codex/shopops-web`. No other service source changed by this worker.

## Outcome

- Both APIs now advertise workspace Bearer authentication and JSON errors in OpenAPI. Chat advertises only `text/event-stream` for a successful POST, with referenced delta/done/error schemas; emitted frames validate against those same models.
- Operations rejects explicitly blank tokens/database paths instead of silently falling back or creating a whitespace-named SQLite file. Startup also closes its initialization connection through the existing connection context.
- Malformed saved provider JSON/session/turn/page/message content is rejected with safe `ProviderError` messages. Existing history remains readable, a new submission returns 502, and its pending predecessor keeps its data and releases its lease. Provider pages validate item shape, boolean continuation, and cursor progression.
- Chat cancellation requires confirmed input acceptance. Preflight and event-stream GET failures cannot cancel an unrelated turn. A coordinator callback durably records uncertain-send intent immediately before either input-bearing POST; ambiguous POST/create failures stay pending without resending or cancelling. Only 2xx establishes acceptance. Existing disconnect cancellation/recovery tests still pass.
- The integration guide records current service/client ownership, route/application/adapter/storage boundaries, runtime configuration, internal service URLs, auth, OpenAPI/SSE contracts, navigation mailbox semantics, lease/recovery timeouts, and extension validation. Backend READMEs link it and describe the repaired behavior.

## Evidence

Initial narrow check: operations new contract suite 7 passed. Chat new suite 4 failed / 2 passed. Exact failing observations: malformed turn/page/text recovery returned HTTP 500 instead of history HTTP 200; rejected preflight issued `POST /v1/agents/sessions/sess_1/events` cancellation after its GET.

Cause: `Chat.recover` indexed missing turn status, provider pagination accepted arbitrary `data`, saved text joined arbitrary values, and `Chat.stream` called `stop(session_id)` unconditionally for unfinished preflight. Repairs validate consumed upstream shapes and gate cancellation on accepted input; no database migration or client response-shape change.

Independent review then found that the initial dispatch guard still recorded intent before opening the GET event stream. Added 10 boundary regressions: 5 failed before refinement. Failed GET opens triggered cancellation and left dispatch intent; ambiguous follow-up POST failures cancelled without confirmed acceptance. The fix moves durable intent into a `before_input` callback immediately before the provider POST, and separately records in-memory acceptance after successful context entry. Further redirect probes demonstrated a follow-up 307 being treated as accepted (`done` instead of `error`); requiring 2xx fixed it. The full boundary suite now contains 12 passing cases, including durability assertions inside the injected HTTP handler before any POST can complete.

Final checks:

| Command and location | Result |
| --- | --- |
| `make ci` in `services/shopops-api` | PASS: dependency setup, Ruff lint/format, **31 tests** |
| `make ci` in `services/shopops-chat-api` | PASS: dependency setup, Ruff lint/format, **53 tests** |
| `git diff --check -- services/shopops-api services/shopops-chat-api docs/service-integration-pattern.md` | PASS |
| Local Markdown target validation for guide and both backend READMEs | PASS: zero missing local links |

Regression coverage includes blank explicit/environment config, invalid Bearer variants with no mutation/provider call, OpenAPI security/error/media schemas, nullable navigation, concurrent navigation IDs, record limit/restart persistence, eleven malformed recovery shapes, preflight/open/POST boundaries, explicit rejection versus ambiguous create/follow-up input, acceptance-only cancellation, and existing root-output/recovery/disconnect flows. Local diff review of the final refinement found no remaining blocking issue in this scope.

`make format` initially stopped at unfinished long lines because the Makefile checks before formatting; direct Ruff formatting resolved them and both full CIs subsequently passed. Both test runs emit the existing Starlette/httpx TestClient deprecation warning. No dependency changes were made solely for that warning.

The untracked whitespace/tab filename under `services/shopops-api` was verified as an empty SQLite database containing only incidents/navigation metadata, then removed. The blank-path regression now changes into its temporary directory, preventing future failed runs from creating that artifact in the service tree.

Docs impact: minor. Guide and backend READMEs updated. Controller can mark integration checkpoint complete and include these results in final plan/journal reconciliation.

## Limits

No servers started, credentials accessed, paid provider calls, commits, deployment, or new external integration. Tests use the real FastAPI factories and SQLite storage with injected HTTP transport. Live OpenAI entitlement, saved-orchestrator tools, deployed proxy/CSP behavior, and browser/UI validation belong to separate checks; the controller owns the workspace browser suite.

Unresolved questions: none for this backend scope.
