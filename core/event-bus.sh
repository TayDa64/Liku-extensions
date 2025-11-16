#!/usr/bin/env bash

set -euo pipefail

LIKUEVENTS="${HOME}/.liku/state/events"
mkdir -p "${LIKUEVENTS}"

liku_event_escape() {
    local text="$1"
    text="${text//\\/\\\\}"
    text="${text//"/\\"}"
    text="${text//$'\n'/\\n}"
    text="${text//$'\r'/\\r}"
    printf '%s' "$text"
}

liku_event_emit() {
    local type="$1"
    local payload="${2:-}"
    local ts
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")"
    local file="${LIKUEVENTS}/$(date +%s%N).event"

    local payload_json
    if [[ "$payload" =~ ^\{.*\}$ || "$payload" =~ ^\[.*\]$ ]]; then
        payload_json="$payload"
    elif [ -z "$payload" ]; then
        payload_json="null"
    else
        payload_json="\"$(liku_event_escape "$payload")\""
    fi

    printf '{"ts":"%s","type":"%s","payload":%s}\n' "$ts" "$type" "$payload_json" > "$file"
}

liku_event_listen() {
    inotifywait -m -e close_write --format '%w%f' "$LIKUEVENTS"
}

liku_event_stream() {
    printf '[Liku] Streaming events from %s\n' "$LIKUEVENTS"

    # Emit existing events first so the user sees recent actions before tailing live updates.
    if compgen -G "${LIKUEVENTS}/*.event" >/dev/null; then
        for file in "${LIKUEVENTS}"/*.event; do
            [ -e "$file" ] || continue
            cat "$file"
        done
    fi

    liku_event_listen | while read -r path; do
        [ -f "$path" ] || continue
        cat "$path"
    done
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    cmd="${1:-}"
    shift || true
    case "$cmd" in
        stream)
            liku_event_stream "$@"
            ;;
        emit)
            type="${1:-}"
            payload="${2:-}"
            if [ -z "$type" ] || [ -z "$payload" ]; then
                printf 'Usage: %s emit <type> <payload>\n' "$0" >&2
                exit 1
            fi
            liku_event_emit "$type" "$payload"
            ;;
        *)
            cat <<'USAGE'
Usage:
  event-bus.sh stream            # stream JSONL events as they arrive
  event-bus.sh emit <type> <payload>
USAGE
            ;;
    esac
fi
