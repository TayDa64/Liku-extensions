#!/usr/bin/env bash

set -euo pipefail

# Ensure no other agent is writing to this terminal
liku_guard_terminal_collision() {
    local term="$1"
    # TODO: implement collision detection
    return 0
}
