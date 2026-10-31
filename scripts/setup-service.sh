#!/usr/bin/env bash
# Put one service's CapRover secrets into the shared GitHub environments of this monorepo.
#
#   scripts/setup-service.sh <service-name> <dev|both>
#
#   dev   develop only: pushes to develop and /deploy deploy it, main skips it
#   both  develop + production: also writes the _PROD_ secrets, so pushes to main deploy it
#
# Values are read from env vars; any that are unset are skipped (set them later in Settings → Environments):
#   CAPROVER_SERVER                         e.g. https://captain.example.com
#   APP_NAME_DEVELOP      CAPROVER_TOKEN_DEVELOP
#   APP_NAME_PRODUCTION   CAPROVER_TOKEN_PRODUCTION   (required with "both")
#   <VAR>_DEVELOP  <VAR>_PRODUCTION         for each name in service.json buildArgVars, e.g. VITE_API_BASE_URL_DEVELOP
#
# Every service shares environment codex-sea-dev (develop) / codex-sea-prod (production); secrets are named
# <SERVICE>_<DEV|PROD>_APP_NAME and <SERVICE>_<DEV|PROD>_CAPROVER_TOKEN, as _build-deploy.yml expects. Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# -eq 2 && "$2" =~ ^(dev|both)$ ]] || { sed -n '2,17p' "$0" >&2; exit 1; }
SERVICE="$1"; TARGET="$2"
[[ -f "${ROOT}/services/${SERVICE}/service.json" ]] || { echo "services/${SERVICE}/service.json not found" >&2; exit 1; }

REPO="$(git -C "${ROOT}" remote get-url origin | sed -E 's#^(git@github\.com:|https://github\.com/)##; s#\.git$##')"
gh auth status >/dev/null

ENVS=(develop)
if [[ "${TARGET}" == "both" ]]; then
  [[ -n "${APP_NAME_PRODUCTION:-}" && -n "${CAPROVER_TOKEN_PRODUCTION:-}" ]] \
    || { echo "\"both\" needs APP_NAME_PRODUCTION and CAPROVER_TOKEN_PRODUCTION" >&2; exit 1; }
  ENVS+=(production)
fi

PREFIX="${SERVICE^^}"; PREFIX="${PREFIX//-/_}"
mapfile -t BUILD_ARG_VARS < <(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1])).get("buildArgVars", [])))' "${ROOT}/services/${SERVICE}/service.json")

for ENV in "${ENVS[@]}"; do
  SUFFIX="${ENV^^}"
  case "${ENV}" in
    develop) KEY=DEV; GH_ENV=codex-sea-dev ;;
    production) KEY=PROD; GH_ENV=codex-sea-prod ;;
  esac
  gh api --silent -X PUT "repos/${REPO}/environments/${GH_ENV}"
  echo "Environment ${GH_ENV}:"
  for pair in "CAPROVER_SERVER:CAPROVER_SERVER" \
              "${PREFIX}_${KEY}_APP_NAME:APP_NAME_${SUFFIX}" \
              "${PREFIX}_${KEY}_CAPROVER_TOKEN:CAPROVER_TOKEN_${SUFFIX}"; do
    secret="${pair%%:*}"; var="${pair#*:}"
    if [[ -n "${!var:-}" ]]; then
      gh secret set "${secret}" --repo "${REPO}" --env "${GH_ENV}" --body "${!var}"
    else
      echo "  - secret ${secret} skipped (\$${var} not set)"
    fi
  done
  # Variables are shared by every service in the environment: two services needing different values
  # for the same name would overwrite each other
  for name in "${BUILD_ARG_VARS[@]}"; do
    [[ -n "${name}" ]] || continue
    var="${name}_${SUFFIX}"
    if [[ -n "${!var:-}" ]]; then
      gh variable set "${name}" --repo "${REPO}" --env "${GH_ENV}" --body "${!var}"
    else
      echo "  - variable ${name} skipped (\$${var} not set)"
    fi
  done
done

echo "Done. Push to develop (or comment /deploy on a PR) to deploy ${SERVICE}."
