# Backend split and orchestrator streaming

Context: plan.md; existing service README/AGENTS. Owner chat_backend. Files: services/shopops-api/** and services/shopops-chat-api/**.

- [x] Preserve operations API and isolate chat service with separate persistence.
- [x] Connect documented saved-agent session lifecycle; serialize turns; root-agent completion only.
- [x] Normalize SSE delta/done/error; persist completed replies; handle interruptions honestly.
- [x] Validate auth, input, provider errors and missing configuration through tests.

Risk: provider account is unavailable in this session; injected transport tests do not prove live API access. Rollback: restore earlier service/client revision; preserve database files before changing schemas.
