# Standalone browser and Telegram-style mobile clients

Context: plan.md; DESIGN-notion.md; explicit user correction requiring independent apps. Owner finish_frontend. Files: services/shopops-web/src/** and package manifests; services/shopops-chat/**.

- [x] Independently built browser5173 and mobile chat5174 apps with direct URLs; no shared application runtime or state.
- [x] Presentation-only viewer5175 embeds both complete cross-origin documents in one tab, with independent reload/open controls and no credentials or app imports.
- [x] Render streaming Markdown tables/code/links safely.
- [x] Chat links publish authenticated navigation mailbox events; separate browser consumes and navigates its own history; external sandbox + new-tab fallback.
- [x] Separate operations API requests; lock/stop/error behavior and regression tests.

Risk: external websites can prohibit embedding. Rollback: revert UI revision without changing saved conversation/operations data.
