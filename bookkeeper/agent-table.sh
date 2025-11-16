#!/usr/bin/env bash

set -euo pipefail

STATE_AGENT_DIR="${HOME}/.liku/state/agents"
declare -a LIKUBOOK_AGENT_ORDER=()
declare -A LIKUBOOK_AGENT_PID
declare -A LIKUBOOK_AGENT_TERMINAL
declare -A LIKUBOOK_AGENT_SESSION
declare -A LIKUBOOK_AGENT_STATUS
declare -A LIKUBOOK_AGENT_COMMAND
declare -A LIKUBOOK_AGENT_MODE
declare -A LIKUBOOK_AGENT_FILE
LIKUBOOK_AGENT_MODES=("interactive" "strict" "resilient" "verbose" "silent")
: "${LIKUBOOK_SELECTED_INDEX:=0}"

liku_tui_collect_agents() {
    LIKUBOOK_AGENT_ORDER=()
    LIKUBOOK_AGENT_PID=()
    LIKUBOOK_AGENT_TERMINAL=()
    LIKUBOOK_AGENT_SESSION=()
    LIKUBOOK_AGENT_STATUS=()
    LIKUBOOK_AGENT_COMMAND=()
    LIKUBOOK_AGENT_MODE=()
    LIKUBOOK_AGENT_FILE=()

    if [ ! -d "$STATE_AGENT_DIR" ] || ! compgen -G "${STATE_AGENT_DIR}"'/*.json' >/dev/null; then
        LIKUBOOK_SELECTED_INDEX=0
        return
    fi

    local file
    for file in "${STATE_AGENT_DIR}"/*.json; do
        [ -e "$file" ] || continue
        local agent
        agent=$(basename "$file" .json)
        mapfile -t _liku_meta < <(python3 - "$file" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text())
print(data.get('pid', ''))
print(data.get('terminalID', ''))
print(data.get('session', ''))
print(data.get('mode', 'interactive'))
PY
        )
        local pid="${_liku_meta[0]}"
        local terminal="${_liku_meta[1]}"
        local session="${_liku_meta[2]}"
        local mode="${_liku_meta[3]}"

        LIKUBOOK_AGENT_ORDER+=("$agent")
        LIKUBOOK_AGENT_PID["$agent"]="$pid"
        LIKUBOOK_AGENT_TERMINAL["$agent"]="$terminal"
        LIKUBOOK_AGENT_SESSION["$agent"]="$session"
        LIKUBOOK_AGENT_MODE["$agent"]="$mode"
        LIKUBOOK_AGENT_FILE["$agent"]="$file"

        local status
        status=$(liku_agent_status "$pid" "$terminal")
        LIKUBOOK_AGENT_STATUS["$agent"]="$status"

        local command
        command=$(liku_agent_command_preview "$terminal")
        LIKUBOOK_AGENT_COMMAND["$agent"]="$command"
    done

    liku_tui_clamp_selection
}

liku_agent_status() {
    local pid="$1"
    local pane="$2"
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        printf 'EXITED'
        return
    fi

    if ! command -v tmux >/dev/null 2>&1 || [ -z "$pane" ]; then
        printf 'RUNNING'
        return
    fi

    local current_cmd
    current_cmd=$(tmux display-message -p -t "$pane" '#{pane_current_command}' 2>/dev/null || printf '')
    case "$current_cmd" in
        '' ) printf 'DETACHED' ;;
        bash|-bash|zsh|-zsh|sh|-sh|fish|-fish) printf 'IDLE' ;;
        *watch*|tail|htop|top) printf 'WATCHING' ;;
        *) printf 'RUNNING' ;;
    esac
}

liku_agent_command_preview() {
    local pane="$1"
    if ! command -v tmux >/dev/null 2>&1 || [ -z "$pane" ]; then
        printf '--'
        return
    fi
    local cmd
    cmd=$(tmux display-message -p -t "$pane" '#{pane_current_command}' 2>/dev/null || printf '')
    if [ -z "$cmd" ]; then
        printf '--'
        return
    fi
    if [ "${#cmd}" -gt 32 ]; then
        printf '%s…' "${cmd:0:31}"
    else
        printf '%s' "$cmd"
    fi
}

liku_tui_clamp_selection() {
    local count="${#LIKUBOOK_AGENT_ORDER[@]}"
    if [ "$count" -eq 0 ]; then
        LIKUBOOK_SELECTED_INDEX=0
        return
    fi
    if [ "$LIKUBOOK_SELECTED_INDEX" -ge "$count" ]; then
        LIKUBOOK_SELECTED_INDEX=$((count - 1))
    elif [ "$LIKUBOOK_SELECTED_INDEX" -lt 0 ]; then
        LIKUBOOK_SELECTED_INDEX=0
    fi
}

liku_tui_move_selection() {
    local delta="$1"
    liku_tui_collect_agents
    local count="${#LIKUBOOK_AGENT_ORDER[@]}"
    if [ "$count" -eq 0 ]; then
        LIKUBOOK_SELECTED_INDEX=0
        return
    fi
    local new_index=$(((LIKUBOOK_SELECTED_INDEX + delta) % count))
    if [ "$new_index" -lt 0 ]; then
        new_index=$((new_index + count))
    fi
    LIKUBOOK_SELECTED_INDEX=$new_index
}

liku_tui_current_agent() {
    liku_tui_collect_agents
    local count="${#LIKUBOOK_AGENT_ORDER[@]}"
    if [ "$count" -eq 0 ]; then
        printf ''
        return 1
    fi
    printf '%s' "${LIKUBOOK_AGENT_ORDER[$LIKUBOOK_SELECTED_INDEX]}"
}

liku_tui_select_agent() {
    local agent
    agent=$(liku_tui_current_agent) || true
    if [ -z "$agent" ]; then
        liku_tui_set_detail "No agents" "Spawn one with \"liku spawn <agent>\"."
        liku_tui_render
        return 1
    fi
    printf '%s' "$agent"
}

liku_agent_cycle_mode() {
    local agent="$1"
    local current="${LIKUBOOK_AGENT_MODE[$agent]:-interactive}"
    local next="$current"
    local i next_index
    for i in "${!LIKUBOOK_AGENT_MODES[@]}"; do
        if [ "$current" = "${LIKUBOOK_AGENT_MODES[$i]}" ]; then
            next_index=$(( (i + 1) % ${#LIKUBOOK_AGENT_MODES[@]} ))
            next="${LIKUBOOK_AGENT_MODES[$next_index]}"
            break
        fi
    done
    liku_agent_store_mode "$agent" "$next"
    LIKUBOOK_AGENT_MODE["$agent"]="$next"
    printf '%s' "$next"
}

liku_agent_store_mode() {
    local agent="$1"
    local mode="$2"
    local file="${LIKUBOOK_AGENT_FILE[$agent]}"
    if [ -z "$file" ] || [ ! -f "$file" ]; then
        return
    fi
    python3 - "$file" "$mode" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
mode = sys.argv[2]
data = json.loads(path.read_text())
data['mode'] = mode
path.write_text(json.dumps(data, indent=2) + '\n')
PY
}

liku_tui_render_agents() {
    liku_tui_collect_agents
    printf ' %-16s %-10s %-10s %-16s %s\n' 'AGENT' 'STATUS' 'MODE' 'TERMINAL' 'CURRENT'
    if [ "${#LIKUBOOK_AGENT_ORDER[@]}" -eq 0 ]; then
        printf ' (no agents registered)\n'
        return
    fi

    local idx name marker
    for idx in "${!LIKUBOOK_AGENT_ORDER[@]}"; do
        name="${LIKUBOOK_AGENT_ORDER[$idx]}"
        marker=' '
        if [ "$idx" -eq "$LIKUBOOK_SELECTED_INDEX" ]; then
            marker='>'
        fi
        printf '%s %-16s %-10s %-10s %-16s %s\n' \
            "$marker" \
            "$name" \
            "${LIKUBOOK_AGENT_STATUS[$name]}" \
            "${LIKUBOOK_AGENT_MODE[$name]}" \
            "${LIKUBOOK_AGENT_TERMINAL[$name]:-n/a}" \
            "${LIKUBOOK_AGENT_COMMAND[$name]}"
    done
}
