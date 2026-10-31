# ShopOps

Monorepo of services deployed to CapRover. Each service lives in `services/<name>/` and has its own
`AGENTS.md` with stack-specific commands, conventions and review checks; read it before working on that service.

## Agent design alignment

- When resuming agent engineering or changing registration, provisioning, session routing, streaming,
  MCP access, or agent-core contracts, first read [agent integration](docs/agent-integration.md)
  and [system architecture](docs/system-architecture.md). Compare the affected code with the target;
  fix drift within the assigned scope and report remaining gaps before claiming completion.
- Keep `agent-core` as the reusable agents-service boilerplate. The product server owns registration
  and requests on-demand per-user teams in OpenAI-hosted environments; do not build one local
  agent-core deployment per user or reuse a shop-shared live team across users.
- Reconcile affected contracts, consumers, and focused checks together. Offline fixtures do not prove
  live hosted provisioning, streaming, or MCP access. Do not treat an older starter spec as authority
  to reverse the confirmed product design.

## Layout

- `services/<name>/` — one deployable service. `service.json` declares `stack` (`go` | `python` | `node`),
  container `port`, and optional `buildArgVars` (GitHub variables passed as Docker build args).
  `make ci` is what CI runs for that service.
- `template/` — templates for new services; `scripts/new-service.sh` copies one into `services/`.
- `.github/workflows/` — shared pipelines for every service (see below). `.github/scripts/changed-services.sh`
  decides which services a change touches.

## Branches and deploy

- Work on feature branches, open PRs into `develop`. CI runs only for services changed in the PR.
- Comment `/deploy` on a PR to deploy its changed services (or `/deploy <svc> ...`) to their develop environment.
- Merge to `develop` deploys the changed services via shared GitHub environment `codex-sea-dev`.
  Merge to `main` deploys every changed service via `codex-sea-prod`, so a service needs its `_PROD_`
  secrets and production CapRover app before it reaches `main`. CapRover secrets are per service:
  `<SVC>_<DEV|PROD>_APP_NAME` / `<SVC>_<DEV|PROD>_CAPROVER_TOKEN`.
- Workflows: `ci.yml` (PR checks), `deploy.yml` (push), `pr-deploy.yml` (`/deploy`), `prune-ghcr.yml` (weekly),
  reusable `_ci.yml` and `_build-deploy.yml`.
- Runtime config comes from env vars set in CapRover App Configs. Never commit `.env`, `captain.json` or secrets.

## Commit messages

- Use `type(scope): message` for every commit; the scope is required.
- Choose the type that describes the change: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`,
  `build`, `perf`, `style` or `chore`.
- Use the affected service name as the scope (e.g. `ping-web`), or the affected shared area
  (e.g. `docs`, `template`, `scripts`, `ci` or `repo`) for changes outside a single service.
- Keep the message concise and describe the change, for example:
  - `feat(ping-web): add service status filter`
  - `fix(ping-api): handle upstream timeout`
  - `docs(template): document Notion-inspired UI guidelines`
  - `chore(docs): reorganize deployment notes`

## CapRover host and domains

- CapRover dashboard / `CAPROVER_SERVER`: `https://captain.cr.ngochoanielts.com`.
- Service domains use `https://<app-name>.cr.ngochoanielts.com`, where `<app-name>` is the CapRover app name.
  Dev: `<service>-dev`, e.g. `https://ping-web-dev.cr.ngochoanielts.com`.
  Production: `<service>`, e.g. `https://ping-web.cr.ngochoanielts.com`.
- Keep deployment secrets pointing to the corresponding CapRover app name (`<service>-dev` for dev,
  `<service>` for production).
- Public services use HTTPS. Internal services (e.g. `ping-2`) use the cluster network and container port;
  enable **Do not expose as web app**, with no public domain or Port Mapping.
- Services call each other over the cluster network at `http://srv-captain--<app-name>:<port>`, where `<port>` is
  the callee's `service.json` port, e.g. `http://srv-captain--ping-2-dev:8000` (dev) /
  `http://srv-captain--ping-2:8000` (production). Never call another service through its public domain.
- The callee's URL is a runtime env var of the caller named `<CALLEE>_URL` (callee name upper-cased, `-` → `_`,
  e.g. `PING_2_URL`), set per app in CapRover App Configs and listed in the caller's `.env.example` with a
  `localhost` value. Code must not default it to a dev app; fail fast when it is missing.
  react-vite frontends name it `API_URL` (nginx `/api/` upstream; `ping-web` predates this and uses `PING_API_URL`).
- Frontends call their API same-origin: the browser requests `/api/...` on the frontend's domain and nginx
  proxies it to the upstream above. Leave `VITE_API_BASE_URL` unset; a full URL there needs CORS on the API.

## Review guidelines

- Write review comments in Vietnamese; keep code identifiers and error messages as-is.
- Only flag issues worth fixing before merge. No style nits that the linter/formatter already covers.
- Treat as P0: leaked secrets/tokens/credentials, auth or permission bypass, injection (SQL, command, path traversal), data loss.
- Treat as P1:
  - Unhandled errors or swallowed exceptions on I/O, DB and HTTP calls.
  - Missing input validation on request handlers.
  - Behavior change without a matching test.
  - Changes to a service's `Dockerfile`, `service.json` or `.github/workflows/*` that could break build or deploy
    (wrong port, missing build arg, widened `permissions`, untrusted input interpolated into `run:`).
  - A change in one service that silently depends on another service's code instead of its API.
  - Another service's URL hardcoded, defaulted to a dev app, or pointed at its public domain instead of
    `srv-captain--<app-name>:<port>` via `<CALLEE>_URL`.
  - New dependencies that are unmaintained, duplicate an existing one, or are pulled in for something trivial.
- Logs must not contain secrets or personal data.
- Note when a PR adds an env var but not to the service's `.env.example` / README.
