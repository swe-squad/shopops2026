---
title: Separate shop clients and backend
date: 2026-10-31
summary: Added independent chat and operations interfaces with a single-workspace persistent API.
---

# Separate shop clients and backend

## What happened
Separated the dashboard and mobile-friendly chat interactions. Added authenticated chat and incident endpoints backed by SQLite.

## Decision
Use one internal service with separate client endpoint families and tables. A persistent writable volume and a workspace token are required. Agent replies and shop integrations are not connected.

## Next steps
Connect trusted identity, shop data, and an agent provider; verify deployment and persistent volume configuration.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
