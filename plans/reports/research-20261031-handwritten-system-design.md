# Handwritten system design: discovery record

Research date: 2026-10-31 (Asia/Ho_Chi_Minh).
Status: Historical discovery record. The subsequent user clarification established the target recorded in [system architecture](../../docs/system-architecture.md) and [product overview](../../docs/project-overview-pdr.md). Questions below capture the earlier interview state, not current product authority.

## Outcome and scope

Understand the author's two handwritten ShopOps sketches, resolve material ambiguities through questions, and then document the agreed system design in this worktree. This discovery covers service responsibilities, data flow, agent capabilities, clients, identity, and action execution. It does not select new technology or change implementation.

The supplied photographs and author clarification are the primary evidence for intended design. Repository documents describe existing decisions and implementation claims; they do not establish that an ambiguous sketch has been approved. External technical research will be scoped after an actual integration or technology question is identified.

## Evidence

- The user supplied Photo 1.jpg (architecture and interfaces) and Photo 2.jpg (services and assignments) in this chat.
- [Existing transcription](../../services/agent-core/imported_sketches_description.md) records these same sketches and explicitly marks uncertain handwriting.
- [Product overview](../../README.md) describes proactive monitoring and the detect, classify, plan, approve, execute, verify, and learn loop.
- [Client workspace](../../docs/client-workspace.md) describes separate browser and Telegram-style web chat clients with an optional presentation viewer.
- [Service integration](../../docs/service-integration-pattern.md) describes the current operations/chat backend boundaries and shared workspace-token access.
- [Agent requirements](../../services/agent-core/agents_api_template_requirements.md) describe an initial per-shop orchestrator assumption, separate user conversations, knowledge/memory MCP, and mock/remote Data MCP. They leave phone authentication, ETL, UI, and shop CRUD to other components.
- [Agent service README](../../services/agent-core/README.md) describes an integrated offline foundation and separately identifies incomplete live-provider integration.

## Provisional reading

The sketches identify eight service responsibilities: Pull Data, Raw Data, Data Mart, Data MCP, Agents Env, Shop interaction, Chat Client, and Web App Client. Whether each is a separate deployment has not been confirmed.

The data diagram connects connectors and processing to raw data, then processing to a data mart. Both data boxes connect to MCP. The agent environment connects to Data MCP and to memory/domain knowledge through an agent-facing MCP band. Agent notes include code execution, skills, tools, context compaction, multiple agents, and an orchestrator.

The interface area names a shop view, BI dashboard, and Telegram chat. The lower sketch includes authentication, PAT, notifications, and links, but overlapping arrows do not establish their complete workflow. The second page says “Auth unique = phone” and contains a crossed-out authentication-service note.

## Decisions to establish

1. Whether this is the complete target architecture, the immediate build scope, or a historical sketch to reconcile with newer decisions.
2. Whether the eight responsibilities are independently deployed services, and how existing agent-core and chat-api relate to Agents Env.
3. Whether Shop interaction owns platform writes, and whether Data MCP exposes reads, writes, or both.
4. Whether Chat Client means an actual Telegram bot, the existing Telegram-style web app, or both.
5. What phone identity, registration, PAT, shop membership, and agent provisioning mean across clients and services.

## Next steps

Kongming independently inspected both photographs and the referenced repository documents. Its review agreed with the provisional reading and identified scope, deployment boundaries, write authority, identity, and client/agent ownership as the first interview topics. No author decisions have been collected yet.

Interview the author and record confirmed answers here. Then update the smallest owning project documentation with the agreed architecture and boundaries, distinguishing intended behavior from verified implementation.

## Unresolved questions

All five decisions above remain open. Team ownership, exact labels near domain knowledge, and the handwritten schedule also need confirmation if they belong in the final documentation.
