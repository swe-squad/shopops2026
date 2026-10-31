# Agent integration checklist

Use this checklist when agent engineering resumes and before changes to registration, provisioning, session routing, streaming, MCP access, or agent-core contracts. [System architecture](system-architecture.md) owns the target; this page connects that intent to integration work. It is a delivery check, not proof that the current foundation is complete.

## Ownership

- **Product server:** authenticate registration, own user identity and the durable user-to-team assignment, and request provisioning on demand. The concrete registration endpoint/owning product-service module still needs selection during integration.
- **agent-core:** reusable agents-service boilerplate for team configuration, managed-provider integration, session/events, recovery, and scoped tools. Do not copy or deploy the whole backend for every user.
- **OpenAI:** run the managed Codex harness and provision the hosted environment requested by the integration.
- **Chat gateway/client:** route authenticated messages to the correct user session and present streamed output and actionable state. Keep provider credentials server-side.
- **MCP services:** independently authorize identity/capability and constrain every query or operation to permitted tenant/shop/product scope.

One component owns each provisioning attempt and session submission. Coordinate through the service API; do not have the product server and agent-core independently create competing teams.

## Check and repair on return

| Check | Inspect and align |
| --- | --- |
| Provisioning ownership | Compare product registration with [agent-core requirements](../services/agent-core/agents_api_template_requirements.md) and [implemented contracts](../services/agent-core/contracts/README.md). Replace any shop-shared live runtime assumption with a user-owned logical team; reusable shop configuration can remain shared. |
| Hosted team | Inspect the [provider adapter](../services/agent-core/README.md) and [chat adapter](../services/shopops-chat-api/app/provider.py). Requests must select the intended OpenAI-hosted environment and configure one orchestrator with 2–3 specialist roles. A concurrency ceiling alone does not prove those roles are configured or used. |
| Duplicate registration / uncertain creation | Persist the assignment and attempt state. Repeated/concurrent registration must converge on one logical team. Reconcile ambiguous external creation before retrying; do not fabricate a ready state. |
| Session ownership | Resolve provider sessions from verified user ownership. A caller cannot select another user's session; shared access to a shop does not share private agent context. |
| Streaming and outputs | Verify initial input and follow-ups reach the same owned session; subscribe before follow-up input. Map provider events to incremental text, final output, failures, tool progress, approvals, and artifacts as required by the UI. See [current chat integration](service-integration-pattern.md). |
| Recovery | Recover saved session state/items after disconnect. Neither EOF nor a specialist's completion proves the orchestrator finished. Avoid duplicate input or shop mutations. |
| MCP connectivity and grants | Verify a reachable authenticated MCP route from the hosted runtime. Preserve independent identity validation and query scoping; private cluster DNS and a phone header alone do not establish that boundary. See [data design](data-and-mcp.md). |
| Inactivity and recall | Treat roughly ten minutes idle as ShopOps' settled-segment archival policy, not a provider timeout. Preserve active work and pending approvals; enforce owner-scoped recall. |

The current chat adapter explicitly creates sessions with `environment.type: none`; this must be aligned before claiming hosted-sandbox delivery. The earlier agent-core spec also defers specialist execution and client-facing SSE. Those are known implementation gaps, not reasons to reverse the confirmed design.

## Evidence before completion

Fix mismatches in the assigned integration scope, including affected contracts, callers, and persistence/recovery behavior. Preserve existing stored data and document migration when ownership changes. Report remaining gaps precisely if another component is needed; do not mark live integration complete based on fixtures.

Run focused owning-service checks first and its required `make ci` after implementation. Demonstrate duplicate-safe registration, cross-user session denial, streamed initial/follow-up output, recovered disconnects, and scoped MCP denial at the real application boundary. Run the existing client integration suite when the changed path crosses the UI.

A live acceptance record must separately show the actual hosted environment, managed team, session continuity, and reachable MCP connection. Offline tests may validate our configuration and failure handling; they cannot establish account access or hosted execution. Keep credentials and private seller data out of evidence.
