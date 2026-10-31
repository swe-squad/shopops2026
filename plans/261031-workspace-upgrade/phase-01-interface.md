# Interface

Read docs/brand, docs/client-workspace.md and each owning AGENTS.md first.

Implement a grid whose tracks permit shrinking: 100dvh parent, minmax(0,1fr) content, min-height:0 down each frame chain. Keep parent overflow hidden; only child content scrolls. At narrow widths offer an accessible view selector, keep hidden child documents mounted. Brand assets are vendored into each deployable service from canonical docs through a checked sync script.

Browser: actual tab state and per-tab navigation, fixed chrome, operations content with explicit empty/loading/error states. Chat: familiar mobile conversation, safe rich output, persistent composer, respectful auto-scroll and recovery.

Validation: meaningful unit tests, lint/build, browser keyboard/scroll/resize/isolation tests, rendered screenshots. Risks: short viewports, hidden frame remounts, background external frames, stale fetch completions. Rollback: revert scoped service changes, preserve persistent data and API contracts.

## Acceptance checklist

- [x] Fixed viewport viewer, preserved child layout/state, independent reload and narrow selector.
- [x] Branded browser tabs, history, drafts, keyboard controls and compact content-first layout.
- [x] Telegram-style chat, safe rich streaming, respectful scrolling and explicit recovery.
- [x] Canonical brand assets and responsive visual evidence.

Evidence: [verification report](reports/verification.md), [browser](reports/browser-client-finish.md), [chat](reports/chat-client-finish.md).
