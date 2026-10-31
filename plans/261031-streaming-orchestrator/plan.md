---
status: completed
---
# Streaming orchestrator and two client workspace

Outcome: two completely standalone apps, displayed together in one tab by a presentation-only viewer loading independent cross-origin documents. Both direct client URLs remain functional. The browser app runs shop operations; the Telegram-style mobile chat app targets the configured OpenAI Agents API orchestrator and streams rich Markdown. Chat links publish navigation requests to the independently running browser app. Both clients and both backend services have distinct entry points and deployment boundaries; the viewer owns only layout.

Constraints: reuse the feature worktree; preserve user changes; keep provider keys server-side; preserve single-workspace bearer access; use real documented Agents API; do not claim live verification without credentials. External websites control their iframe permissions.

Non-goals: production identity/multi-tenant rollout, shop-platform ingestion, deployment or configuring real secrets.

Acceptance: independently built shopops-web and shopops-chat apps with separate origins; a third viewer embedding full app documents in one tab without business state/credentials; separate backend services; streamed delta/done/error behavior; GFM tables/code/URLs; authenticated persistent navigation mailbox consumed by browser; independent reload/lock; abort/error handling; backend persistence/contract tests; frontend interaction tests; embedded and direct browser inspection.

Trade-offs: the earlier shared-React-shell interpretation was rejected by the user. User confirmed a visual preview of a third viewer embedding two standalone documents. Cross-origin framing preserves independent app runtime/state while sharing viewing space, at the cost of a third static deployable and explicit CSP embedding permissions. A small operations-owned authenticated mailbox allows clients to coordinate without window-opener assumptions or cross-origin bearer sharing. It assumes one workspace; multi-user targeting needs scoped identity. External websites may refuse the full ancestor chain and retain a new-tab fallback.

Better approaches: none — standalone client apps are the explicit accepted direction.

Phases: provider/API split; standalone clients and rich streaming; independent-document viewer and embedding policy; navigation mailbox/proxy/deployment docs; integration review and verification. Source owners: finish_backend services/shopops-api + shopops-chat-api; finish_frontend clients and then shopops-workspace; controller client embedding configs/docs; reviewer read-only. Preview confirmation recorded in chat; advisory report plans/reports/research-20261031-independent-client-viewer.md.
