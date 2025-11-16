#!/usr/bin/env bash

set -euo pipefail

liku_agent_state_set() {
    mkdir -p "${HOME}/.liku/state/agents"
    printf '%s\n' "$2" > "${HOME}/.liku/state/agents/$1.state"
}

liku_agent_state_get() {
    cat "${HOME}/.liku/state/agents/$1.state"
}
