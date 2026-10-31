# Phase 2: Temporary marts, integrations and deployment

Status: pending. Estimate: 4-6 days. Owner: service implementer; operator provisions runtime secrets and infrastructure. Dependencies: Phase 1 and agreed raw-approval/ingestion/processing APIs. Context: [plan](plan.md), [configuration](../../docs/shop-data-mcp-configuration.md).

## Requirements and steps

- [ ] Remind owner that ingestion/processing and owner-approval integrations do not yet exist. Obtain authentication, request/response schemas, callback verification, retry/idempotency and job/watermark contracts. Never implement fabricated live success.
- [ ] Implement create/query/drop temporary marts through controlled result materialization. Execute SELECT with the restricted source identity, then write bounded typed results with a separate writer. Inherit every source grant, sensitivity, ownership and expiry through joins and derived results.
- [ ] Implement TTL cleanup and quotas with immediate access denial on expiry/revocation even when deletion is delayed. Keep lifecycle independent of PostgreSQL connection-local TEMP objects.
- [ ] Connect approval status/callbacks to the trusted owner identity; verify signatures and replay protection. Denial, timeout and revocation must remain denied.
- [ ] Implement automatic refresh against the actual collector API. Enforce shop/resource/window/quota limits, deduplicate retries and track raw/processing/mart stages without releasing raw payloads. Wire processing explicitly if the collector does not trigger it.
- [ ] Update service README and `.env.example` to match real service names and callee URL conventions. Reconcile any approved config changes in the configuration guide.
- [ ] Operator creates `shop-data-mcp-dev`, private PostgreSQL access and verified TLS, configures issuer/credentials and dev deployment secrets. Never deploy production or expose PostgreSQL ports.
- [ ] Product backend supplies scoped authorization during Agents API session creation; verify renewals and an actual tool discovery/query round trip through public HTTPS.

## Verification and ownership

Modify only `services/shop-data-mcp/**` plus its owning docs. Deployment scripts and workflows remain shared existing infrastructure unless an evidenced incompatibility requires review. Run `make ci` and the PostgreSQL integration target introduced by Phase 1. Exercise workspace joins without shop columns, raw-derived expiry/revocation, quota exhaustion, delayed cleanup, duplicate pulls and failed/partial processing. Run the configuration guide's release checks on dev.

Extension trace: mart-only and raw-derived temporary datasets share result handles and query shapes; the latter additionally enforce raw-grant dependencies. Prove this boundary by querying the same derived-result chain before and after grant revocation. No unrestricted raw permissions may be inherited by the mart-only path.

Success: all requested capabilities work with real contracts; credentials are absent from agent context/logs; external traffic cannot bypass auth; PostgreSQL remains private. Record sanitized deployment evidence and outstanding limits. On isolation failures, disable traffic, revoke affected access and roll back the image; do not restore/drop source data as an application rollback.
