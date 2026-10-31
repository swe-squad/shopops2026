# Agents API Starter Template — Basic Requirements

## 1. Objective

Create a reusable template for the Agents component using **OpenAI Agents API**. The template must support development with mock data and allow integration with real services later.

Confirmed target: **one dedicated logical agent team per registered user**, with one orchestrator and 2–3 specialists in OpenAI-hosted environments reserved for that user. The product server owns registration and requests provisioning using this boilerplate. This supersedes the earlier per-shop assumption; existing code/contracts still require the [integration alignment work](../../docs/agent-integration.md).

## 2. Functional Requirements

### 2.1. Orchestrator

- Accept user requests and determine how to handle them.
- Coordinate data retrieval, knowledge and memory access, and user responses.
- Ask follow-up questions when essential information is missing.
- Allow configuration of instructions, the model, and MCP connections.

### 2.2. Memory: Sessions and History

- Create and continue conversation sessions.
- Preserve context for follow-up questions.
- Persist conversation history and support retrieval.
- Keep history separated by shop and user.
- Store the mapping between application conversations and Agents API sessions.

### 2.3. Domain Knowledge

- Load predefined business knowledge from configuration files or documents, such as JSON or Markdown.
- Track the version of the knowledge bundle in use.
- Allow each orchestrator to select its knowledge bundle through configuration.
- Provide knowledge retrieval and search through MCP.

### 2.4. Multi-Agent Scenarios

Support the following three scenarios:

| Scenario | Responsibility |
| --- | --- |
| Retrieve data from the Data Mart | Call Data MCP tools and use their results to answer the request. |
| Interact with knowledge and memory | Retrieve relevant business knowledge or conversation history. |
| Interact with the user | Receive requests, ask for missing information, and present results. |

The orchestrator owns user interaction and must support delegation to specialist agents when needed. Each request should invoke only the capabilities it needs.

### 2.5. MCP Integration

- Provide a **Knowledge–Memory MCP** interface for knowledge and history retrieval.
- Include a **mock Data MCP** with deterministic sample data for independent development.
- Make endpoints, authentication settings, and tool access configurable.
- Use the same input and output contracts for mock and real services.
- Return clear errors for missing data, insufficient permissions, and connection failures.

### 2.6. Registration and Provisioning

- Accept a trusted product-server request to provision a registered user's team in an OpenAI-hosted environment; shop access is a separate authorization dimension.
- Associate the instance with its template, knowledge bundle, and MCP configuration.
- Return an `orchestrator_id`.
- Handle repeated registration requests without creating duplicate user teams or retrying an uncertain provider creation blindly.
- Create a separate session for each conversation.

## 3. Minimum Application API

| Capability | Purpose |
| --- | --- |
| Provision user team | Create or return the registered user's logical team and its provisioning state. |
| Create conversation | Start a new application conversation. |
| Send message | Submit a request or continue a conversation. |
| Get events or results | Retrieve progress and final responses. |
| Get history | Retrieve previous conversation messages. |
| Health check | Check whether the service is running. |

## 4. Required Configuration and Integration Inputs

- **OpenAI:** API key and model.
- **Identity:** `tenant_id`, `user_id`, and access permissions supplied by the authentication system; development fixtures may be used initially.
- **Data MCP:** endpoint, authentication configuration, tool schemas, and sample data.
- **Knowledge:** knowledge bundle and version.
- **Storage:** persistence for orchestrator configuration, session mappings, and history.

Secrets must be supplied through environment variables or the system's secret management mechanism.

## 5. Template Deliverables

- Source code organized into clear modules.
- Sample configuration and an `.env.example` file.
- Sample orchestrator instructions.
- A sample domain knowledge bundle and mock Data MCP.
- Integration contracts for the other teams.
- A README covering local setup, demo execution, and connection to real services.
- Basic tests for the main workflows.

## 6. Acceptance Criteria

The template must demonstrate that:

1. Product-server registration provisions a user-owned team; repeated requests return the same logical assignment, and another user cannot access its live session or environment.
2. A user can ask for business data and receive the expected result from the mock Data MCP.
3. A user can ask a business question and receive an answer grounded in the sample knowledge bundle.
4. Follow-up questions retain the relevant conversation context.
5. History can be retrieved only within the permitted shop and user scope.
6. Missing information and tool failures produce appropriate responses or statuses.
7. Real MCP endpoints can be configured for new integration sessions.

## 7. Initial Scope

The first version covers the Agents backend and the components needed to demonstrate its workflows.

The complete user interface, ETL and Data Mart implementation, phone-based authentication, and shop CRUD operations are owned by the other components of the system.

## 8. Hosted Runtime Extension — 2026-10-31

The next template milestone must use the Managed Codex Harness through Agents API with an `openai_hosted` sandbox, actual Python execution, versioned approved skills, two harness-created specialist roles, and scoped downloadable report artifacts. Keep the existing `none` profile for compatibility; its live smoke establishes only the conversation/tool baseline.

The application retains identity, persistence and internal MCP function handlers. Specialists analyze validated root-supplied evidence because the current API does not support function tools in subagents. Do not expose private cluster endpoints or backend credentials to the sandbox.

Normative design, limits and acceptance AC15–AC22: [Managed runtime spec](agents_api_managed_runtime_spec.md). Implementation ownership, difficulty and separate worktrees: [T05–T08 in the task tracker](task-tracker/task_list.md#hosted-runtime-extension-t05t08). The original addition was documentation only; current T05–T08 modules are integrated offline and hosted live acceptance remains unaccepted with exact evidence gaps recorded. See the tracker for verification and live evidence.
