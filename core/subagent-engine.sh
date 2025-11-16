#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "${SCRIPT_DIR}/event-bus.sh"
source "${SCRIPT_DIR}/cli-environment.sh"

# Spawn a new subagent inside the correct CLI/TUI context.
liku_spawn_agent() {
    local agent_name="$1"
    if [ -z "$agent_name" ]; then
        printf '[Liku] Provide an agent name to spawn.\n' >&2
        exit 1
    fi

    local agent_dir="${HOME}/.liku/agents/${agent_name}"
    if [ ! -d "$agent_dir" ]; then
        printf '[Liku] Agent "%s" not found under %s.\n' "$agent_name" "$agent_dir" >&2
        exit 1
    fi

    liku_cli_require_tmux
    liku_cli_capture_environment

    local session
    session="$(liku_cli_target_session_name)"
    local pane

    if liku_cli_is_tmux; then
        pane=$(tmux split-window -P -F "#{pane_id}" -c "$agent_dir")
    else
        liku_cli_ensure_tmux_session "$session"
        pane=$(tmux new-window -P -F "#{pane_id}" -t "$session" -n "$agent_name" -c "$agent_dir")
    fi

    tmux send-keys -t "$pane" "./run.sh" C-m

    local pid
    pid=$(tmux display-message -p -t "$pane" "#{pane_pid}")

    mkdir -p "${HOME}/.liku/state/agents"
    cat > "${HOME}/.liku/state/agents/${agent_name}.json" <<EOF
{
  "agent": "${agent_name}",
  "terminalID": "${pane}",
  "session": "${session}",
  "tty": "$(liku_cli_current_tty)",
  "term": "$(liku_cli_term)",
    "pid": "${pid}",
    "mode": "interactive"
}
EOF

    local payload
        payload=$(printf '{"agent":"%s","terminalID":"%s","session":"%s","tty":"%s","term":"%s","mode":"interactive"}' \
                "$agent_name" "$pane" "$session" "$(liku_cli_current_tty)" "$(liku_cli_term)")
    liku_event_emit "agent.spawn" "$payload"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    cmd="${1:-}"
    shift || true
    case "$cmd" in
        spawn)
            liku_spawn_agent "${1:-}"
            ;;
        *)
            printf 'Usage: %s spawn <agent-name>\n' "$0" >&2
            exit 1
            ;;
    esac
fi
