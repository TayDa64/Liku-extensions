#!/usr/bin/env bash

set -euo pipefail

liku_tui_select_agent() {
    ls "${HOME}/.liku/state/agents" | head -n 1
}

liku_tui_render_agents() {
    printf 'AGENT\tSTATE\n'
    for f in "${HOME}/.liku/state/agents"/*.json; do
        [ -e "$f" ] || continue
        local name
        name=$(basename "$f" .json)
        printf '%s\t%s\n' "$name" "running"
    done
}
