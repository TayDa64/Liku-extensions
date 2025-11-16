#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/cli-environment.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/event-bus.sh"

LIKUTMUX_PANE_STATE_DIR="${HOME}/.liku/state/panes"
mkdir -p "${LIKUTMUX_PANE_STATE_DIR}"

liku_tmux_agent_session_name() {
    printf '%s-agent' "$(liku_cli_session_key)"
}

liku_tmux_ensure_agent_session() {
    liku_cli_require_tmux
    local session
    session="$(liku_tmux_agent_session_name)"
    if ! tmux has-session -t "$session" 2>/dev/null; then
        local cols lines
        cols=$(tput cols 2>/dev/null || printf '120')
        lines=$(tput lines 2>/dev/null || printf '32')
        tmux new-session -d -s "$session" -x "$cols" -y "$lines"
        tmux rename-window -t "$session:0" 'general'
        tmux new-window -t "$session" -n 'background'
        tmux new-window -t "$session" -n 'logging'
        tmux new-window -t "$session" -n 'sandbox'
    fi
    local window
    for window in general background logging sandbox; do
        liku_tmux_ensure_window "$session" "$window"
    done
}

liku_tmux_ensure_window() {
    local session="$1"
    local window="$2"
    if ! tmux list-windows -t "$session" -F '#{window_name}' | grep -Fx "$window" >/dev/null 2>&1; then
        tmux new-window -t "$session" -n "$window"
    fi
}

liku_tmux_idle_command() {
    local cmd="$1"
    case "$cmd" in
        ''|bash|-bash|zsh|-zsh|sh|-sh|fish|-fish) return 0 ;;
        *) return 1 ;;
    esac
}

liku_tmux_find_idle_pane() {
    local session="$1"
    local window="$2"
    local panes
    if ! panes=$(tmux list-panes -t "$session:$window" -F '#{pane_id} #{pane_current_command}' 2>/dev/null); then
        return 1
    fi
    local line pane cmd
    while IFS= read -r line; do
        pane="${line%% *}"
        cmd="${line#* }"
        if liku_tmux_idle_command "$cmd"; then
            printf '%s' "$pane"
            return 0
        fi
    done <<<"$panes"
    return 1
}

liku_tmux_create_pane() {
    local session="$1"
    local window="$2"
    local cwd="$3"
    tmux split-window -P -F '#{pane_id}' -t "$session:$window" -c "$cwd"
}

liku_tmux_format_command() {
    if [ "$#" -eq 0 ]; then
        printf ''
        return
    fi
    local formatted=""
    while [ "$#" -gt 0 ]; do
        formatted+="$(printf '%q' "$1") "
        shift || true
    done
    formatted="${formatted% }"
    printf '%s' "$formatted"
}

liku_tmux_status_from_command() {
    local cmd="$1"
    case "$cmd" in
        ''|bash|-bash|zsh|-zsh|sh|-sh|fish|-fish) printf 'IDLE' ;;
        *watch*|tail|htop|top) printf 'WATCHING' ;;
        *) printf 'RUNNING' ;;
    esac
}

liku_tmux_state_file() {
    local pane="$1"
    local safe="${pane//[%]/_}"
    printf '%s/pane-%s.json' "$LIKUTMUX_PANE_STATE_DIR" "$safe"
}

liku_tmux_record_execution() {
    local pane="$1"
    local command="$2"
    local cwd="$3"
    local label="$4"
    local info
    info=$(tmux display-message -p -t "$pane" '#{pane_id} #{pane_index} #{pane_pid} #{window_id} #{window_index} #{window_name} #{session_name} #{pane_current_command}' 2>/dev/null || true)
    if [ -z "$info" ]; then
        return
    fi
    read -r pane_id pane_index pane_pid window_id window_index window_name session_name pane_cmd <<<"$info"
    local status
    status=$(liku_tmux_status_from_command "$pane_cmd")
    local terminal_id
    terminal_id=$(printf '%s:%s.%s' "$session_name" "$window_index" "$pane_index")
    local ts
    ts=$(date -Iseconds)
    local state_file
    state_file="$(liku_tmux_state_file "$pane_id")"
    python3 - "$state_file" "$pane_id" "$pane_index" "$pane_pid" "$window_id" "$window_index" "$window_name" "$session_name" "$pane_cmd" "$status" "$terminal_id" "$ts" "$command" "$cwd" "$label" <<'PY'
import json, sys
from pathlib import Path
file = Path(sys.argv[1])
payload = {
    "pane_id": sys.argv[2],
    "pane_index": sys.argv[3],
    "pane_pid": sys.argv[4],
    "window_id": sys.argv[5],
    "window_index": sys.argv[6],
    "window_name": sys.argv[7],
    "session_name": sys.argv[8],
    "pane_command": sys.argv[9],
    "status": sys.argv[10],
    "terminal_id": sys.argv[11],
    "timestamp": sys.argv[12],
    "last_command": sys.argv[13],
    "cwd": sys.argv[14],
    "label": sys.argv[15],
}
file.write_text(json.dumps(payload, indent=2) + "\n")
PY
}

liku_tmux_emit_exec_event() {
    local pane="$1"
    local command="$2"
    local cwd="$3"
    local info
    info=$(tmux display-message -p -t "$pane" '#{pane_id} #{window_name} #{session_name} #{pane_pid} #{window_index} #{pane_index}' 2>/dev/null || true)
    if [ -z "$info" ]; then
        return
    fi
    read -r pane_id window_name session_name pane_pid window_index pane_index <<<"$info"
    local terminal_id
    terminal_id=$(printf '%s:%s.%s' "$session_name" "$window_index" "$pane_index")
    local payload
    payload=$(python3 - "$pane_id" "$window_name" "$session_name" "$pane_pid" "$terminal_id" "$command" "$cwd" <<'PY'
import json, sys
print(json.dumps({
    "pane": sys.argv[1],
    "window": sys.argv[2],
    "session": sys.argv[3],
    "pid": sys.argv[4],
    "terminalID": sys.argv[5],
    "command": sys.argv[6],
    "cwd": sys.argv[7],
}))
PY
    )
    liku_event_emit "command.exec" "$payload"
}

liku_tmux_exec_command() {
    if [ "$#" -eq 0 ]; then
        printf '[Liku] Provide a command to execute.\n' >&2
        exit 1
    fi
    local target_window="general"
    local cwd="$PWD"
    local label=""
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --window)
                target_window="${2:-general}"
                shift 2
                ;;
            --cwd)
                cwd="${2:-$cwd}"
                shift 2
                ;;
            --label)
                label="${2:-}"
                shift 2
                ;;
            --)
                shift
                break
                ;;
            -*)
                printf '[Liku] Unknown option for exec: %s\n' "$1" >&2
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done
    if [ "$#" -eq 0 ]; then
        printf '[Liku] Provide a command to execute.\n' >&2
        exit 1
    fi
    local -a cmd
    cmd=("$@")
    liku_cli_capture_environment
    liku_tmux_ensure_agent_session
    local session
    session="$(liku_tmux_agent_session_name)"
    liku_tmux_ensure_window "$session" "$target_window"
    local pane
    pane=$(liku_tmux_find_idle_pane "$session" "$target_window" || true)
    if [ -n "$pane" ]; then
        tmux send-keys -t "$pane" "$(printf 'cd %q' "$cwd")" C-m
    else
        pane=$(liku_tmux_create_pane "$session" "$target_window" "$cwd")
    fi
    local command_string
    command_string=$(liku_tmux_format_command "${cmd[@]}")
    tmux send-keys -t "$pane" "$command_string" C-m
    liku_tmux_record_execution "$pane" "$command_string" "$cwd" "${label:-$target_window}"
    liku_tmux_emit_exec_event "$pane" "$command_string" "$cwd"
    printf '[Liku] Executing in %s (%s)\n' "$pane" "${session}:${target_window}"
}

liku_tmux_list_panes() {
    if ! compgen -G "${LIKUTMUX_PANE_STATE_DIR}/pane-*.json" >/dev/null; then
        printf '[Liku] No recorded pane metadata. Use "liku exec" to start commands.\n'
        return
    fi
    printf 'TERMINALID\tSTATUS\tLAST COMMAND\tUPDATED\n'
    local file
    for file in "${LIKUTMUX_PANE_STATE_DIR}"/pane-*.json; do
        [ -e "$file" ] || continue
        python3 - "$file" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text())
print(f"{data.get('terminal_id','?')}\t{data.get('status','?')}\t{data.get('last_command','')}\t{data.get('timestamp','')}")
PY
    done
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    cmd="${1:-}"
    shift || true
    case "$cmd" in
        exec)
            liku_tmux_exec_command "$@"
            ;;
        list)
            liku_tmux_list_panes "$@"
            ;;
        *)
            cat <<'USAGE'
Usage:
  tmux-agent.sh exec [--window <name>] [--cwd <path>] [--label <text>] -- <command>
  tmux-agent.sh list
USAGE
            ;;
    esac
fi
