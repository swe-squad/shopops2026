#!/usr/bin/env bash
# Scaffold a new service in this monorepo from template/<template> + template/_shared.
#
#   scripts/new-service.sh <template> <service-name>
#
# Creates services/<service-name>/. Templates: any directory under template/ except _shared.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATES="${ROOT}/template"

usage() {
  echo "Usage: $(basename "$0") <template> <service-name>" >&2
  echo "Templates: $(find "${TEMPLATES}" -mindepth 1 -maxdepth 1 -type d ! -name '_*' -printf '%f ' | sort)" >&2
  exit 1
}

[[ $# -eq 2 ]] || usage
TEMPLATE="$1"; NAME="$2"

[[ -d "${TEMPLATES}/${TEMPLATE}" && "${TEMPLATE}" != _* ]] || { echo "Unknown template: ${TEMPLATE}" >&2; usage; }
# Must be valid as a GHCR image name, GitHub environment prefix and CapRover app name
[[ "${NAME}" =~ ^[a-z][a-z0-9-]{1,48}[a-z0-9]$ ]] || { echo "Invalid service name '${NAME}': use lowercase letters, digits and '-' (3-50 chars)" >&2; exit 1; }

# owner/repo of this monorepo, from git@github.com:<owner>/<repo>.git or https://github.com/<owner>/<repo>
REMOTE="$(git -C "${ROOT}" remote get-url origin 2>/dev/null | sed -E 's#^(git@github\.com:|https://github\.com/)##; s#\.git$##')"
[[ "${REMOTE}" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]] || { echo "Cannot read GitHub owner/repo from the origin remote" >&2; exit 1; }
OWNER="${REMOTE%%/*}"

OUT="${ROOT}/services/${NAME}"
[[ ! -e "${OUT}" ]] || { echo "services/${NAME} already exists" >&2; exit 1; }

mkdir -p "${OUT}"
cp -a "${TEMPLATES}/_shared/." "${OUT}/"
cp -a "${TEMPLATES}/${TEMPLATE}/." "${OUT}/"

# Go module path first (it contains the other placeholders), then the plain placeholders
grep -rlI --null -e '__SERVICE_NAME__' -e '__GITHUB_OWNER__' "${OUT}" \
  | xargs -0 -r sed -i \
      -e "s#github.com/__GITHUB_OWNER__/__SERVICE_NAME__#github.com/${REMOTE}/services/${NAME}#g" \
      -e "s/__SERVICE_NAME__/${NAME}/g" \
      -e "s/__GITHUB_OWNER__/${OWNER}/g"

cat <<EOF
Created services/${NAME}
  template: ${TEMPLATE}
  image:    ghcr.io/${OWNER,,}/${NAME}
  port:     $(sed -nE 's/.*"port": *([0-9]+).*/\1/p' "${OUT}/service.json")
Next: scripts/setup-service.sh ${NAME} <dev|both>   (GitHub environment + CapRover secrets)
EOF
