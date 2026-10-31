#!/bin/sh
set -eu
: "${API_URL:?API_URL must point to the ShopOps API}"

# The optional viewer is an origin only; reject nginx/CSP interpolation characters.
if [ -n "${WORKSPACE_VIEWER_URL:-}" ]; then
    case "$WORKSPACE_VIEWER_URL" in
        *[!a-zA-Z0-9.:/-]*) echo 'WORKSPACE_VIEWER_URL contains invalid origin characters' >&2; exit 1 ;;
    esac
    if ! printf '%s' "$WORKSPACE_VIEWER_URL" | LC_ALL=C grep -Eq '^(https://[A-Za-z0-9][A-Za-z0-9.-]*|http://(localhost|127[.]0[.]0[.]1))(:[0-9]{1,5})?$'; then
        echo 'WORKSPACE_VIEWER_URL must be an HTTPS origin (or local HTTP origin)' >&2
        exit 1
    fi
    viewer_authority=${WORKSPACE_VIEWER_URL#*://}
    case "$viewer_authority" in
        *:*) viewer_port=${viewer_authority##*:}
             if [ "$viewer_port" -lt 1 ] || [ "$viewer_port" -gt 65535 ]; then
                 echo 'WORKSPACE_VIEWER_URL has an invalid port' >&2
                 exit 1
             fi ;;
    esac
fi
