---
title: Independent clients in one viewer tab
date: 2026-10-31
summary: "Built standalone browser and Telegram-style chat clients, separate APIs, and a presentation-only cross-origin viewer."
---

# Independent clients in one viewer tab

## What happened
The original shared React shell did not match the intended independent-client boundary. Clarification established standalone Telegram-style web chat, then the user confirmed a visual preview of one viewer tab loading the complete browser and chat documents on different origins.

## Delivery
Added chat Agents API session streaming and persistent state, an operations navigation mailbox, independent client builds, and a layout-only workspace viewer. The viewer receives no app tokens and imports neither application. Explicit per-client CSP allows the configured viewer origin.

## Verification
Backend tests cover provider lifecycle and operations persistence/navigation. Client tests cover streaming Markdown, URL delivery, stop/lock and independent frame reloads. Real local navigation worked between separate origins and within the viewer. Review caught multi-line origin validation and a narrow-view grid overflow; both were fixed. Docker and live OpenAI account calls were unavailable.

## Next
Configure a saved orchestrator and runtime credentials privately, provision dev apps/volumes and verify deployed CSP and live provider behavior. AgentWiki publish skipped.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
