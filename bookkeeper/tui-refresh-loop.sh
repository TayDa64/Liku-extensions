#!/usr/bin/env bash

set -euo pipefail

LIKUBOOK_DETAIL_TITLE=""
declare -a LIKUBOOK_DETAIL_LINES=()

liku_tui_init_state() {
    : "${LIKUBOOK_SELECTED_INDEX:=0}"
    liku_tui_set_detail \
        "Welcome" \
        "Use ↑/↓ to focus an agent." \
        "Press G to send guidance or L to inspect logs."
}

liku_tui_set_detail() {
    local title="$1"
    shift || true
    LIKUBOOK_DETAIL_TITLE="$title"
    LIKUBOOK_DETAIL_LINES=()
    if [ "$#" -eq 0 ]; then
        LIKUBOOK_DETAIL_LINES+=(" ")
        return
    fi
    while [ "$#" -gt 0 ]; do
        LIKUBOOK_DETAIL_LINES+=("$1")
        shift || true
    done
}

liku_tui_render_detail() {
    printf '\n-- %s --\n' "$LIKUBOOK_DETAIL_TITLE"
    if [ "${#LIKUBOOK_DETAIL_LINES[@]}" -eq 0 ]; then
        printf '(no details available)\n'
        return
    fi
    local line
    for line in "${LIKUBOOK_DETAIL_LINES[@]}"; do
        printf '%s\n' "$line"
    done
}

liku_tui_render() {
    clear
    liku_tui_layout
    liku_tui_render_agents
    liku_tui_render_detail
}
