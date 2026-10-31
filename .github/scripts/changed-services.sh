#!/usr/bin/env bash
# Print a JSON array of services (dirs under services/ that have a service.json) changed between two commits.
#
#   changed-services.sh <base> <head>
#
# An empty, all-zero or unknown base (first push of a branch) selects every service.
set -euo pipefail

base="${1:-}"
head="${2:-HEAD}"

all="$(find services -mindepth 2 -maxdepth 2 -name service.json -printf '%h\n' 2>/dev/null | xargs -r -n1 basename | sort)"

if [[ -z "${base}" || "${base}" =~ ^0+$ ]] || ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
  list="${all}"
else
  changed="$(git diff --name-only "${base}...${head}" -- services | cut -d/ -f2 | sort -u)"
  list="$(comm -12 <(printf '%s\n' "${all}") <(printf '%s\n' "${changed}"))"
fi

jq -cn --arg l "${list}" '$l | split("\n") | map(select(length > 0))'
