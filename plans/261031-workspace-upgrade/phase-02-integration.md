# Integration foundation

Keep operations and chat backend engines independent. Inspect existing validation, persistence, stream lifecycle and documented API shapes. Repair demonstrated defects and add regression tests. Do not connect new services or use live provider credentials.

Document route → service/adapter → persistence boundaries, runtime internal service URLs, explicit timeouts/cancellation, authentication and input/output models. Extend only when a real feature needs an adapter. Explain navigation mailbox, SSE lifecycle and local single-workspace limitations. Document extension ownership and checklists alongside existing setup docs.

Validation: both backend CIs and contract/lifecycle tests. Rollback preserves existing databases and routes.

## Acceptance checklist

- [x] Independent persistent APIs and typed authentication/error/SSE contracts.
- [x] Verified provider dispatch, cancellation and uncertain-outcome recovery boundaries.
- [x] Documented feature ownership, adapter/persistence patterns and real integration limitations.

Evidence: [backend report](reports/backend-20261031-integration-foundation.md), [verification report](reports/verification.md).
