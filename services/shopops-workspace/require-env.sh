#!/bin/sh
set -eu

# Validate the whole value before interpolating public origins into nginx JSON/CSP.
validate_origin() {
    value=$1
    case "$value" in ''|*[!a-zA-Z0-9.:/-]*) return 1 ;; esac
    if ! printf '%s\n' "$value" | grep -Eq '^(https://[a-zA-Z0-9][a-zA-Z0-9.-]*(:[0-9]{1,5})?|http://(localhost|127\.0\.0\.1)(:[0-9]{1,5})?)$'; then
        return 1
    fi
    scheme=${value%%://*}
    authority=${value#*://}
    host=${authority%%:*}
    port=''
    case "$authority" in
        *:*)
            port=${authority##*:}
            [ "$port" -ge 1 ] && [ "$port" -le 65535 ] || return 1
            ;;
    esac
    if ! printf '%s\n' "$host" | awk '
        length($0) > 253 { exit 1 }
        {
            count = split($0, labels, ".")
            for (i = 1; i <= count; i++) {
                if (length(labels[i]) < 1 || length(labels[i]) > 63 || labels[i] !~ /^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$/) exit 1
            }
            if ($0 ~ /^[0-9.]+$/) {
                if (count != 4) exit 1
                for (i = 1; i <= count; i++) {
                    if (labels[i] + 0 > 255 || (length(labels[i]) > 1 && substr(labels[i], 1, 1) == "0")) exit 1
                }
            } else if (labels[count] ~ /^[0-9]+$/) exit 1
        }
    '; then
        return 1
    fi
    canonical_host=$(printf '%s' "$host" | tr '[:upper:]' '[:lower:]')
    printf '%s://%s' "$scheme" "$canonical_host"
    if [ -n "$port" ] && ! { [ "$scheme" = https ] && [ "$port" -eq 443 ]; } && ! { [ "$scheme" = http ] && [ "$port" -eq 80 ]; }; then
        printf ':%s' "$port"
    fi
}

: "${BROWSER_APP_URL:?BROWSER_APP_URL must point to the standalone browser app origin}"
: "${CHAT_APP_URL:?CHAT_APP_URL must point to the standalone chat app origin}"

browser_origin=$(validate_origin "$BROWSER_APP_URL") || { echo 'BROWSER_APP_URL must be an HTTPS hostname origin, or HTTP localhost/127.0.0.1 with an optional valid port.' >&2; exit 1; }
chat_origin=$(validate_origin "$CHAT_APP_URL") || { echo 'CHAT_APP_URL must be an HTTPS hostname origin, or HTTP localhost/127.0.0.1 with an optional valid port.' >&2; exit 1; }
[ "$browser_origin" != "$chat_origin" ] || { echo 'Browser and chat apps must have different origins.' >&2; exit 1; }

