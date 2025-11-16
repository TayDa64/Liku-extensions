#!/usr/bin/env bash

set -euo pipefail

LIKUEVENTS="${HOME}/.liku/state/events"
mkdir -p "${LIKUEVENTS}"

liku_event_emit() {
    local type="$1"
    local payload="$2"
    local file="${LIKUEVENTS}/$(date +%s%N).event"

    printf '{"type":"%s","payload":"%s"}\n' "$type" "$payload" > "$file"
}

liku_event_listen() {
    inotifywait -m -e create "$LIKUEVENTS"
}
