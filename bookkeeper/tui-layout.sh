#!/usr/bin/env bash

set -euo pipefail

liku_tui_layout() {
    if command -v liku_cli_env_summary >/dev/null 2>&1; then
        liku_cli_env_summary
    fi
    printf 'Commands: [R]efresh [K]ill [G]uidance [Q]uit\n'
}
