#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_DIR="${HOME}/.liku/core"

if [ -f "${CORE_DIR}/cli-environment.sh" ]; then
    # shellcheck disable=SC1090
    source "${CORE_DIR}/cli-environment.sh"
fi

if [ -f "${CORE_DIR}/event-bus.sh" ]; then
    # shellcheck disable=SC1090
    source "${CORE_DIR}/event-bus.sh"
fi

source "${SCRIPT_DIR}/hotkeys.sh"
source "${SCRIPT_DIR}/agent-table.sh"
source "${SCRIPT_DIR}/tui-refresh-loop.sh"
source "${SCRIPT_DIR}/tui-input-loop.sh"
source "${SCRIPT_DIR}/tui-layout.sh"

liku_bookkeeper_start() {
    if command -v liku_cli_supports_tui >/dev/null 2>&1; then
        if ! liku_cli_supports_tui; then
            printf '[Liku] Terminal %s cannot render the Bookkeeper TUI. Switch to a full-featured terminal (TERM=%s).\n' \
                "$(liku_cli_current_tty)" "$(liku_cli_term)" >&2
            exit 1
        fi
    fi

    liku_tui_init_state
    clear
    liku_tui_render
    liku_tui_input_loop
}

liku_bookkeeper_start "$@"
