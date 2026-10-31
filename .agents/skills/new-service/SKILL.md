---
name: new-service
description: Add a new service (go-gin, python-fastapi, react-vite) to this monorepo under services/ from the repo's templates; CI/CD to GHCR and CapRover is shared and picks it up automatically. Optionally sets up its GitHub environment + CapRover secrets. Use when the user asks to create/scaffold/add a new service, project, app, API or frontend, e.g. "new-service go-gin payment-api" or "tạo service react-vite admin-web".
---

# New service

This repo is a monorepo: every service lives in `services/<name>/` and shares the workflows in
`.github/workflows/`. Adding a service = adding its directory; no workflow changes needed.
Run scripts from the repo root.
Use the deployment host and domain conventions in the root [AGENTS.md](../../../AGENTS.md),
section **CapRover host and domains**, when preparing setup commands and service URLs.

## Inputs

| Input | Required | Notes |
|---|---|---|
| template | yes | A directory under `template/` not starting with `_`. Today: `go-gin`, `python-fastapi`, `react-vite`. Map loose wording: "go"/"gin" → `go-gin`, "python"/"fastapi"/"py" → `python-fastapi`, "react"/"vite"/"frontend"/"fe" → `react-vite`. |
| service name | yes | lowercase, digits, `-`; 3–50 chars. Becomes the directory, GHCR image `ghcr.io/<owner>/<name>`, secret prefix (`payment-api` → `PAYMENT_API_DEV_*`), CapRover app suggestion. Normalize obvious cases (`Payment API` → `payment-api`) and tell the user. |
| environments | yes | `dev` (develop only) or `both` (develop + production). Map "dev"/"chỉ dev"/"test" → `dev`, "prod"/"production"/"cả hai"/"dev và prod" → `both`. There is no prod-only: every change passes through `develop` first, so a service always has a dev app. |
| exposure | no | `public` (domain + HTTPS) or `internal` (only reachable by other apps). Default: `public` for react-vite, otherwise ask. Map "nội bộ"/"internal"/"backend only" → `internal`. |
| api | react-vite only | The service its `/api/` proxy forwards to (e.g. `ping-api`). Becomes the runtime `API_URL`. If the frontend has no backend, remove the `location /api/` block from `nginx.conf` and `require-env.sh` + its `COPY` from the `Dockerfile`. |

Ask once, in a single question, for whatever of these is missing (for environments: "Service này chỉ chạy dev,
hay cả dev + prod?"). Do not ask about anything else up front.

## Steps

1. **Scaffold**
   ```bash
   scripts/new-service.sh <template> <name>
   ```
   Creates `services/<name>/` (refuses if it exists). Owner/repo come from the `origin` remote.

2. **Verify locally**: `make ci` inside `services/<name>` — the same command CI runs.
   Skip only if the toolchain is missing, and say so. Remove build output afterwards (`bin/`, `dist/`, `.venv/`).

3. **GitHub environment + secrets**: give the user the command for the chosen environments and let them run
   it, so tokens never pass through the chat. Do not run it yourself.
   ```bash
   # dev
   CAPROVER_SERVER=https://captain.cr.ngochoanielts.com APP_NAME_DEVELOP=<name>-dev CAPROVER_TOKEN_DEVELOP=... \
     scripts/setup-service.sh <name> dev

   # both
   CAPROVER_SERVER=https://captain.cr.ngochoanielts.com APP_NAME_DEVELOP=<name>-dev CAPROVER_TOKEN_DEVELOP=... \
   APP_NAME_PRODUCTION=<name> CAPROVER_TOKEN_PRODUCTION=... \
     scripts/setup-service.sh <name> both
   ```
   - All services share GitHub environments `codex-sea-dev` (develop) and `codex-sea-prod` (production).
     The script writes `CAPROVER_SERVER`, `<NAME>_DEV_APP_NAME`, `<NAME>_DEV_CAPROVER_TOKEN` (and the `_PROD_`
     pair for `both`), where `<NAME>` is the service name upper-cased with `-` → `_`.
   - Pushes to `main` deploy every changed service to production. With `dev`, warn the user that merging the
     service to `main` will fail its deploy job until the `_PROD_` secrets exist.
   - For every name in `service.json` `buildArgVars`, pass `<VAR>_DEVELOP` / `<VAR>_PRODUCTION`; they become
     environment variables used as Docker build args, shared by all services in that environment, so warn if
     another service already uses the same name with a different value.
   - Exception: react-vite's `VITE_API_BASE_URL` stays **unset**. The browser calls `/api/` on the frontend's own
     domain and nginx forwards it to `API_URL` inside the cluster; a value there makes the browser call the API
     directly, which fails on CORS ("Failed to fetch").
   - Never echo tokens back or write them to files.

4. **Commit and deploy**: commit `services/<name>` (ask before pushing). Pushing to `develop`, or a PR
   merged into it, deploys every changed service; `/deploy` on a PR deploys the PR's services. With `both`, run
   *Deploy* manually on `main` once for the first production deploy.

5. **Report**: path, template, image, port, what was verified, which secrets are still missing, the address
   (public: `https://<app>.cr.ngochoanielts.com`; internal: `http://srv-captain--<app>:<port>`), and the
   CapRover checklist below.

## CapRover checklist (manual, per environment)

- Create the app `<name>-dev` (and `<name>` when environments is `both`) and enable **App Token** under Deployment.
- Set **Container HTTP Port** to `port` in `service.json` (go-gin `8080`, python-fastapi `8000`, react-vite `80`).
  This port is inside the container only: CapRover routes by subdomain, so dev and prod apps, and different
  services, can all use the same port on one VPS. Do not reserve port ranges and do not add **Port Mapping**.
- Set the runtime env vars the image requires in **App Configs** before the first deploy; without them the
  container exits on start (react-vite: `API_URL=http://srv-captain--<api>-dev:<port>`, or `<api>` for production).
- For public services, connect the service domain according to root `AGENTS.md` and enable HTTPS.
  For internal services, enable **Do not expose as web app**; no public domain or Port Mapping is needed.
- If another service calls this one, set `<NAME>_URL=http://srv-captain--<app>:<port>` in the **caller's** App
  Configs (`<name>-dev` app for dev, `<name>` for production) and add it to the caller's `.env.example`, as in
  root `AGENTS.md`.
- The GHCR registry in CapRover → Cluster must be able to read `ghcr.io/<owner>/*` (PAT with `read:packages`).
- Runtime env vars (DB URLs, etc.) go in CapRover App Configs, not in the image.

## How the pipeline works (for answering follow-up questions)

- `.github/scripts/changed-services.sh <base> <head>`: JSON list of `services/<x>` (with `service.json`)
  changed in `base...head`; empty/zero/unknown base → all services.
- `ci.yml`: on PRs, `make ci` per changed service (matrix) via reusable `_ci.yml`, which sets up the
  toolchain from `service.json` `stack`.
- `_build-deploy.yml` (reusable): `_ci.yml` → build `services/<svc>` → push `ghcr.io/<owner>/<svc>:<sha7>`
  + moving tag → CapRover using `<SVC>_<DEV|PROD>_APP_NAME` / `_CAPROVER_TOKEN` from shared environment
  `codex-sea-dev` / `codex-sea-prod`. Queued per service+env.
- `deploy.yml`: push to `develop` → changed services to develop; push to `main` → changed services to
  production. Manual run takes a services list (empty = all).
- `pr-deploy.yml`: `/deploy` or `/deploy svc1 svc2` on a PR (owner/member/collaborator, not forks) →
  PR head to develop (tag `pr-<n>`), reacts 🚀 and comments the result.
- `prune-ghcr.yml`: weekly, per service image keeps the 10 newest versions plus whatever `latest-*` points to.
- Codex review: root `AGENTS.md` review guidelines + the service's own `AGENTS.md`; enabled once for the repo.

## Adding a new template

Create `template/<name>/` with the app, `Dockerfile`, `.dockerignore`, `.gitignore`, `Makefile` with a `ci`
target, `service.json` (`stack` must be one `_ci.yml` knows — add a setup step there for a new stack — plus
`port`, optional `buildArgVars`) and `AGENTS.md` (stack notes + `## Review guidelines (<stack>)`).
Use `__SERVICE_NAME__` / `__GITHUB_OWNER__` placeholders; Go module paths `github.com/__GITHUB_OWNER__/__SERVICE_NAME__`
are rewritten to `github.com/<owner>/<repo>/services/<name>`. Update the template list here and in `README.md`.
