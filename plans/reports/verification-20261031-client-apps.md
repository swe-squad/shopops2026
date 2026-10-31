# Client app verification

Date: 2026-10-31 (Asia/Ho_Chi_Minh).

## Current verified foundation

- Operations API: 18 tests, lint/format pass. Persistence, auth, legacy message retention, monotonic latest-navigation mailbox and unsafe URL rejection covered.
- Chat API: 20 tests, lint/format pass after scoped simplification. Injected HTTP transport covers documented saved-agent requests, streamed root output and final-text corrections, failure/cancellation/persistence/recovery behavior. No real OpenAI call was made.
- Standalone browser frontend: 4 tests; lint and production build pass.
- Standalone Telegram-style chat frontend: 19 tests; lint and production build pass. Fragmented UTF-8/SSE, terminal errors, Markdown, URL filtering, stop/lock, link retry covered.
- Real local navigation: browser at 127.0.0.1:5173 and chat at localhost:5174 unlocked independently with test-only credential. Chat message history was injected solely for browser QA. Clicking /shop/incidents posted to the real operations API on8000, persisted ID1, and browser polling changed the browser URL within its own origin. Browser DOM mounted no chat; chat DOM mounted no browser.
- Standalone visual checks at375/390,768 and1440 showed no outer horizontal overflow; screenshots inspected. A mobile brand touch-target warning was corrected.
- Both client startup scripts: allowed empty/exact configured origin; rejected multiline/control/quote/path/query/userinfo/bad-port/remote-HTTP cases. Independent reviewer reproduced42 cases successfully.
- Independent code review: no unresolved substantive backend or standalone-client finding. Simplifier made two behavior-preserving backend edits and reran both suites.

## Viewer verification

The user confirmed a visual preview of a presentation-only third viewer embedding full cross-origin client documents.

- Viewer: 50 tests cover runtime config, invalid origins/interpolation characters, load errors and independent frame reloads; lint/build pass.
- Real viewer on localhost:5175 loaded browser127.0.0.1:5173 and chatlocalhost:5174 with distinct origins. Both child attempts to read parent.document were blocked by same-origin policy. Viewer own DOM contained no input controls.
- Injected streamed chat reply rendered a Markdown table; clicking its local link posted through the real operations service and updated the embedded browser to its own /shop/incidents route. No outer-tab navigation occurred.
- Reload browser control relocked only the browser document. Chat table and composer stayed available, proving independent runtime/session lifecycle.
- Independent review of viewer source and48 runtime validation cases found no unresolved issue. Client CSP validation passed42 independent cases.
- Layout diagnostic at768 and1440 had no findings. A39px overflow at375 was traced to the grid's intrinsic minimum and fixed using minmax(0,1fr) and frame width constraints. The375px diagnostic was rerun and reported0 errors/0 warnings; document width equalled viewport width.

The screenshot uses an explicitly labelled sample stream for browser verification; application runtime has no fixture fallback. Both direct client URLs remain functional.

## Limits

Docker daemon unavailable, so container image/nginx runtime execution was not verified. Python checks used local3.12.8 while deployment manifest targets3.14. Physical mobile keyboard behavior and live OpenAI project/saved-agent access remain unverified. No deployment or secrets configured.
