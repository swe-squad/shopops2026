# Plan: RAM mock connectors

User authorized autonomous implementation and a PR into develop. Branch: `feat/shopops-web-mock-connectors`.

## Architecture

One Node HTTP mock process in the shopops-web container, proxied by nginx at `/api/mock/`. State is a two-entry object, shared for this demo only. Node supervises nginx: either child/server failure terminates the container; SIGTERM stops both. Local Vite mounts the same handler with its own RAM state. No persistence, external OAuth, or operations service changes.

Trust boundary: untrusted HTTP path/method/origin to public, non-sensitive demo flags. Allowlist platforms, reject cross-origin mutations, never pass credentials to mock, never use flags to authorize operations.

## Ordered slices

1. **HTTP mock contract (S, no dependencies)** — handler + tests under `services/shopops-web/mock/`. GET defaults false, PUT is idempotent and platform-specific, new handler resets state; invalid requests rejected. Verify with `npm --prefix services/shopops-web test -- mock/`, then service build/tests. Stage only these files.
2. **Runtime integration (M, depends on 1)** — Vite plugin, Node entrypoint, Docker/nginx startup. Same API in dev/container; port 80, health, existing proxy and CSP preserved. Verify service CI, HTTP smoke and container build/lifecycle when available. Stage runtime/config files.
3. **Connector UI (split into state/component then routing/style, depends on 1)** — hook/API consumer + focused tests, then Connections/success pages in browser navigation. Keep tab drafts/history and independent platform state. Verify focused UI tests, service tests/build after each part. Stage each verified part.
4. **Browser regression and docs (M, depends on 2–3)** — adapt initial-page expectations, add actual HTTP connector flow, reload/relogin/second-browser and viewport coverage. Update service docs and task status. Verify browser suite, CI, brand drift, runtime checks.
5. **Review and delivery (depends on 4)** — inspect tests and diff for correctness/security/runtime impact, mutation-check one assertion, resolve findings. Commit scoped changes, push feature branch, create PR into develop with exact validation/limitations.

## Risks

- nginx-only image currently lacks Node: add runtime and supervision, test child failure/shutdown and startup errors.
- Mock state is global per process and resets on restart: document and test, no implied account isolation.
- Initial page changes existing tests: preserve business assertions by navigating explicitly to Overview in relevant regressions.
- Docker daemon currently unavailable: investigate starting an isolated owned daemon; if unavailable, record limitation and verify runtime locally.

## Checkpoints

After slices 1–2: tested API and runnable runtime, existing UI intact. After slice 3: full UI flow passes service checks. Before commit/PR: browser regression and review completed, limitations documented.
