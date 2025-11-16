#!/usr/bin/env bash

set -euo pipefail

liku_key_R() {
    liku_tui_render
}

liku_key_K() {
    local agent
    agent=$(liku_tui_select_agent)
    liku_event_emit "agent.kill" "$agent"
}

liku_key_G() {
    local agent
    agent=$(liku_tui_select_agent)
    liku_event_emit "agent.elicit" "$agent"
}
