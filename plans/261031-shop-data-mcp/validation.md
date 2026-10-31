# Plan validation evidence

Date: 2026-10-31. Scope: documentation and implementation-plan validation, not runtime verification.

| Phase | Claim | Evidence | Result |
|---|---|---|---|
| 1 | Python scaffold is available | `template/python-fastapi/AGENTS.md` | Verified |
| 1 | Python service uses port 8000 | `template/python-fastapi/service.json` | Verified |
| 1 | CI entry point is make ci | `template/python-fastapi/Makefile`, target `ci` | Verified |
| 1 | Service creation script exists | `scripts/new-service.sh` | Verified |
| 1 | Agent mart contract is available in this branch | Previously inspected `data_mock_sample/mart/README.md` is absent from this worktree | Unverified dependency |
| 2 | Setup script is available | `scripts/setup-service.sh` | Verified |
| 2 | Cluster address convention is documented | `AGENTS.md`, CapRover host and domains | Verified |
| 2 | Shared dev environment is codex-sea-dev | `AGENTS.md`, Branches and deploy | Verified |
| 2 | Agents API supports service-origin authenticated HTTP MCP | [official guide](https://developers.openai.com/api/docs/guides/agents-api/tools/mcp) | Verified |
| 2 | Configuration release checks cover isolation, grants and refresh stages | `docs/shop-data-mcp-configuration.md` | Verified |

Repository and official documentation checked in this session. User confirmed the three deployment/integration questions; no answer was inferred. Proposed files, env names and endpoints are marked planned, not claimed existing.

Finding resolved during drafting: the prior setup explanation used one generic database user. The configuration contract distinguishes control, shop-bound query and workspace writer credentials, and makes credential resolution a prerequisite. Ingestion/processing variables remain provisional until real service names are supplied. Runtime security is not established by this document review.

Additional finding: sample data inspected in the original checkout was not tracked in the base revision and is absent from this worktree. Supply an approved schema/catalog fixture before Phase 1; do not rely on those local files being present.

Remaining dependencies: actual database schema/version/TLS route, issuer/owner approval, collector and processing contracts. Remind owner before implementation and before accepting live traffic. Recommendation: documentation is ready for PR; implementation/deployment remains gated on those inputs.
