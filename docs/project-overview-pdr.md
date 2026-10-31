# ShopOps product intent

ShopOps helps Shopee sellers move from manually watching dashboards to resolving operational issues with evidence and seller control. The promise is **Know what needs attention. Know what to do next.** See the [brand direction](brand/brand-direction.md) and [voice principles](brand/voice-and-copy.md).

## Who and why

Primary users are small and midsize Shopee sellers in Vietnam: teams of 1–5 handling roughly 20–500 orders per day. Agencies managing several shops are secondary users.

Today, sellers act as their own on-call team. Seller Center provides data, but sellers must notice issues, understand causes, choose a response, and check whether it worked. Delays can leak profit and damage account health. ShopOps should reduce that burden without taking away the seller's judgment.

## Product loop

**Detect → Classify → Plan → Seller Chooses → Execute → Verify → Learn**

| Stage | Product requirement and reason |
| --- | --- |
| Detect | Proactively spot review spikes, repeated product complaints, negative-margin vouchers, rising cancellations or returns, penalties, late shipments, stock-versus-demand risks, and payout or fee anomalies. Surface issues early enough to act. |
| Classify | Group related signals into an incident with evidence, likely cause, affected scope, severity, urgency, and estimated impact. Distinguish confirmed facts from hypotheses so the seller can judge the recommendation. |
| Plan | Offer 2–3 meaningful responses with expected impact, cost, risk, reversibility, and required permissions. Make trade-offs visible instead of forcing one answer. |
| Seller Chooses | Let the seller choose, reject, or adjust an option through chat buttons and conversation. A recommendation is not authorization. |
| Execute | Apply the chosen action through an available real API or an explicitly identified mock server. Respect the chosen scope and permission boundary; report failures honestly. |
| Verify | Let the agent propose success metrics and a suitable observation window. Compare outcomes with a baseline; an accepted API request alone does not prove the business problem is resolved. |
| Learn | Use verified outcomes and seller feedback to improve future recommendations and the autonomy permitted for that issue/action. |

For example, repeated complaints about a shirt fitting too tightly should become an incident about sizing, supported by the relevant evidence. Proposed responses must make their trade-offs clear; ShopOps must not silently infer permission to change the listing or spend money.

## Conversation and workspace

**Telegram-first chat is the shared triage channel.** ShopOps can initiate a conversation when it detects an issue; the seller can initiate one to ask questions, explain context, or request an investigation. The conversation carries evidence, options, decisions, execution status, and outcome checks.

The web workspace complements chat with business intelligence, detailed evidence, and a view of the shop that reflects confirmed mutations. It gives the seller enough context to inspect a recommendation or verify what changed without making dashboard watching the main operating model.

The current Telegram-style web chat is a demonstration client, distinct from the intended Telegram channel. [Client workspace](client-workspace.md) owns the current client boundaries; [system architecture](system-architecture.md) distinguishes implemented connections from target runtime design and integration gaps.

## Trust grows by issue and action

Autonomy is specific to an issue/action and its authorized scope. Reliability in one task must not become a blanket grant over the shop.

| Level | Seller control |
| --- | --- |
| Suggest only | Present evidence and options; wait for the seller's choice before execution. |
| Auto-execute with notification | Execute previously authorized action types, notify the seller, and support rollback where the integration makes it possible. |
| Silent low-risk execution | Execute low-risk actions within explicit prior authorization without routine approval or notification for each occurrence. |

Rollback limits must be clear when choosing an action. Trust comes from useful recommendations and verified results; silence or past acceptance is not a new permission grant. Keep the evidence and decision trail available even when routine notifications are suppressed.

## Runtime design decisions

Each registered user should receive a dedicated, isolated team hosted by OpenAI: one orchestrator and 2–3 specialists. This is the intended runtime design, not a claim that registration or team provisioning is already implemented. Isolation keeps one user's shop context, memory, and permissions separate; the orchestrator gives the seller one coherent conversation.

MCP is a critical boundary for domain knowledge, persistent memory, semantic retrieval of archived turns, shop data reads, and separately authorized shop writes. This separation lets the team retain useful context without confusing knowledge retrieval with permission to mutate a shop. Concrete boundaries and current owners belong in [system architecture](system-architecture.md).

Codex supports development and is used selectively at runtime for complex work, tool integration, code, or debugging when that capability is useful. Routine triage should remain understandable and proportionate to the seller's problem.

## Hackathon scope and evidence

Keep the demonstration simple while showing the whole decision loop and its trust boundaries. A clearly labeled mock integration is acceptable evidence of the interaction design; it is not evidence of live Shopee access, a live Telegram bot, successful real-world remediation, or provisioned per-user teams.

The goal is a proactive operations companion that helps resolve an issue and checks the result. Keep the hackathon focused on that loop and seller-defined control. Preserve the intended product principles when documenting implementation gaps.

A convincing demonstration should show a detected issue, supporting evidence, alternative actions, a seller decision, an attributable execution result, and a baseline/outcome comparison. The web view should reflect confirmed shop changes. Business benefit is less manual triage, earlier response to profit and account-health risks, and trust earned through observable results; do not invent measured gains.
