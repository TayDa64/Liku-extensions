#!/usr/bin/env bash

set -euo pipefail

liku_tui_layout() {
    if command -v liku_cli_env_summary >/dev/null 2>&1; then
        liku_cli_env_summary
    fi
    printf 'Commands: ↑/↓ Select | [R]efresh | [D]etails | [L]ogs | [G]uide | [A]utofix | [P]ause | [C]ontinue | [S]et mode | [W]indow | [K]ill | [Q]uit\n'
    printf '\n'
}
