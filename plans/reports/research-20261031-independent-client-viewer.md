# Independent clients in one tab

Researched 2026-10-31 (Asia/Ho_Chi_Minh). Scope: compose the existing standalone browser and Telegram-style web clients without merging runtime, state or backend boundaries.

Recommendation: a third presentation-only viewer loads each app in a cross-origin iframe. Keep direct client URLs, builds and per-app memory authentication. Preserve the existing operations-owned navigation mailbox; the viewer needs no tokens or postMessage bridge.

Evidence: MDN defines iframes as nested browsing contexts with separate documents; same-origin policy restricts cross-origin script access. Each child can restrict allowed parents using HTTP Content-Security-Policy frame-ancestors, which checks every ancestor. Configure a narrow viewer-origin allowlist and viewer frame-src limited to its client origins; verify deployment headers for conflicting X-Frame-Options. Third-party cookies are a future embedded-auth concern; current per-app memory bearer credentials avoid a shared cookie dependency.

Alternatives: mounting app components in a shared React root couples runtime/state and violates the clarified intent. Same-origin path reverse proxy can retain separate builds but weakens origin isolation and adds base-path/API-routing complexity. Independent cross-origin documents are the smallest fit.

Verified existing behavior: two frontends compile independently; real local mailbox test navigates browser5173 from chat5174. Chat20 and operations18 tests pass; frontend web4 and chat19 tests pass. OpenAI live account access and production iframe headers remain unverified.

Sources:
- https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe
- https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors
- https://developer.mozilla.org/en-US/docs/Web/Privacy/Guides/Third-party_cookies

Kongming independently recommends the third viewer and cautions against claiming native emulator, separate browser-profile or process isolation. No implementation changes made under this advisory stage. Preview: ../261031-streaming-orchestrator/visuals/explain-independent-clients.html.

Next: confirm visual outcome with user, then resume cook to add viewer and verify both embedded and standalone routes.

Unresolved: user confirmation of proposed viewer presentation; live iframe policy headers after deployment.
