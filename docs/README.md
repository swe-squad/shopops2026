# ShopOps documentation

Start with the [project introduction](../README.md). Product and architecture pages describe the confirmed target; setup guides and service contracts describe the existing implementation. Plans and research preserve evidence, not product authority.

## Understand the solution

| Question | Owning document |
| --- | --- |
| What are we building for the hackathon? | [Project write-up (PDF)](ShopOps-WIP-project-write-up.pdf) · [Editable Markdown](project-write-up.md) |
| Who is this for, and what should it achieve? | [Product overview](project-overview-pdr.md) |
| How do managed agents, sessions, and services fit together? | [System architecture](system-architecture.md) |
| How are MCP access, shop data, and private memory guarded? | [Data and MCP design](data-and-mcp.md) |
| What should ShopOps look and sound like? | [Brand kit](brand/README.md) |

## Build and operate

| Question | Owning document |
| --- | --- |
| How do I run the browser, chat, and viewer? | [Client workspace](client-workspace.md) |
| How should registration and the agent boilerplate be integrated? | [Agent integration checklist](agent-integration.md) |
| Where does a client feature belong? | [Feature development](feature-development.md) |
| How do services integrate and recover from failures? | [Service integration](service-integration-pattern.md) |
| How does CI/CD reach CapRover? | [Deployment flow](deploy-flow.md) |
| What does a particular service implement? | Its README, `AGENTS.md`, and contracts under [services](../services/) |

The root [AGENTS.md](../AGENTS.md) owns collaboration/review rules. Each service owns its commands, runtime configuration, schemas, and tests. Follow links to those owners instead of copying their details into new project guides.

## Keep the route small

Update the owning page when a decision changes. Target architecture does not silently amend executable API contracts: reconcile the contract and its consumers during delivery. Keep branding in the existing brand kit and deployment guidance in the deployment guide.

[Plans and reports](../plans/) hold dated investigations, proposals, and verification records. The [original sketch transcription](../services/agent-core/imported_sketches_description.md) preserves uncertain handwriting; confirmed product intent belongs to the overview and architecture above. Avoid using old task completion notes as proof that a live integration works.
