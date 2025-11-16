#!/usr/bin/env bash

set -euo pipefail

liku_key_R() {
    liku_tui_render
}

liku_key_up() {
    liku_tui_move_selection -1
    liku_tui_render
}

liku_key_down() {
    liku_tui_move_selection 1
    liku_tui_render
}

liku_key_K() {
    local agent
    agent=$(liku_tui_select_agent) || return
    liku_event_emit "agent.kill" "$agent"
    liku_tui_set_detail "Kill signal" "Sent SIGTERM request to ${agent}."
    liku_tui_render
}

liku_key_G() {
    local agent
    agent=$(liku_tui_select_agent) || return
    local guidance
    guidance=$(liku_bookkeeper_prompt_line "Guidance for ${agent} (enter to cancel):") || return
    if [ -z "$guidance" ]; then
        liku_tui_set_detail "Guidance" "Cancelled."
        liku_tui_render
        return
    fi
    liku_bookkeeper_emit_event "agent.elicit" "$agent" "instructions" "$guidance"
    liku_tui_set_detail "Guidance sent" "Forwarded instructions to ${agent}."
    liku_tui_render
}

liku_key_D() {
    local agent
    agent=$(liku_tui_select_agent) || return
    local pid="${LIKUBOOK_AGENT_PID[$agent]:-unknown}"
    local session="${LIKUBOOK_AGENT_SESSION[$agent]:-n/a}"
    local pane="${LIKUBOOK_AGENT_TERMINAL[$agent]:-n/a}"
    local status="${LIKUBOOK_AGENT_STATUS[$agent]:-unknown}"
    local mode="${LIKUBOOK_AGENT_MODE[$agent]:-interactive}"
    local command="${LIKUBOOK_AGENT_COMMAND[$agent]:---}"
    liku_tui_set_detail \
        "Agent ${agent}" \
        "PID: ${pid}" \
        "Session: ${session}" \
        "Terminal: ${pane}" \
        "Status: ${status}" \
        "Mode: ${mode}" \
        "Current command: ${command}"
    liku_tui_render
}

liku_key_L() {
    local agent
    agent=$(liku_tui_select_agent) || return
    liku_bookkeeper_show_logs "$agent"
}

liku_key_A() {
    local agent
    agent=$(liku_tui_select_agent) || return
    local suggestion
    suggestion=$(liku_bookkeeper_prompt_line "Autofix suggestion for ${agent}:") || return
    if [ -z "$suggestion" ]; then
        liku_tui_set_detail "Autofix" "No suggestion provided."
        liku_tui_render
        return
    fi
    liku_bookkeeper_emit_event "agent.autocorrect" "$agent" "suggestion" "$suggestion"
    liku_tui_set_detail "Autofix" "Suggestion queued for ${agent}."
    liku_tui_render
}

liku_key_P() {
    local agent pid
    agent=$(liku_tui_select_agent) || return
    pid="${LIKUBOOK_AGENT_PID[$agent]:-}"
    if [ -z "$pid" ]; then
        liku_tui_set_detail "Pause failed" "No PID recorded for ${agent}."
        liku_tui_render
        return
    fi
    if kill -STOP "$pid" 2>/dev/null; then
        liku_tui_set_detail "Paused" "Sent SIGSTOP to ${agent}."
    else
        liku_tui_set_detail "Pause failed" "Could not send SIGSTOP to ${agent}."
    fi
    liku_tui_render
}

liku_key_C() {
    local agent pid
    agent=$(liku_tui_select_agent) || return
    pid="${LIKUBOOK_AGENT_PID[$agent]:-}"
    if [ -z "$pid" ]; then
        liku_tui_set_detail "Resume failed" "No PID recorded for ${agent}."
        liku_tui_render
        return
    fi
    if kill -CONT "$pid" 2>/dev/null; then
        liku_tui_set_detail "Resumed" "Sent SIGCONT to ${agent}."
    else
        liku_tui_set_detail "Resume failed" "Could not resume ${agent}."
    fi
    liku_tui_render
}

liku_key_S() {
    local agent next_mode
    agent=$(liku_tui_select_agent) || return
    next_mode=$(liku_agent_cycle_mode "$agent")
    liku_tui_set_detail "Mode updated" "${agent} now runs in ${next_mode} mode."
    liku_tui_render
}

liku_key_W() {
    local agent pane
    agent=$(liku_tui_select_agent) || return
    pane="${LIKUBOOK_AGENT_TERMINAL[$agent]:-}"
    if [ -z "$pane" ]; then
        liku_tui_set_detail "No pane" "${agent} does not expose a tmux pane."
        liku_tui_render
        return
    fi
    if command -v tmux >/dev/null 2>&1 && liku_cli_is_tmux; then
        if tmux select-pane -t "$pane" 2>/dev/null; then
            liku_tui_set_detail "Pane focused" "Active tmux pane switched to ${agent}."
        else
            liku_tui_set_detail "Pane selection failed" "Unable to select ${pane}."
        fi
    else
        liku_tui_set_detail "tmux hint" "Run: tmux select-pane -t ${pane}"
    fi
    liku_tui_render
}

liku_bookkeeper_prompt_line() {
    local prompt="$1"
    printf '\n%s ' "$prompt"
    local input
    if ! IFS= read -r input </dev/tty; then
        printf '\n' >&2
        return 1
    fi
    printf '\n'
    printf '%s' "$input"
}

liku_bookkeeper_emit_event() {
    local type="$1"
    local agent="$2"
    local field="$3"
    local message="$4"
    local payload
    payload=$(python3 - <<'PY' "$agent" "$field" "$message"
import json, sys
agent = sys.argv[1]
field = sys.argv[2]
message = sys.argv[3]
payload = {"agent": agent}
if field:
    payload[field] = message
print(json.dumps(payload))
PY
    )
    liku_event_emit "$type" "$payload"
}

liku_bookkeeper_show_logs() {
    local agent="$1"
    local pane="${LIKUBOOK_AGENT_TERMINAL[$agent]:-}"
    if ! command -v tmux >/dev/null 2>&1; then
        liku_tui_set_detail "Logs unavailable" "tmux is not installed."
        liku_tui_render
        return
    fi
    if [ -z "$pane" ]; then
        liku_tui_set_detail "Logs unavailable" "${agent} is not linked to a pane."
        liku_tui_render
        return
    fi
    local raw
    if ! raw=$(tmux capture-pane -p -S -50 -t "$pane" 2>/dev/null); then
        liku_tui_set_detail "Logs unavailable" "Unable to capture pane ${pane}."
        liku_tui_render
        return
    fi
    local lines=()
    if [ -n "$raw" ]; then
        while IFS= read -r line; do
            lines+=("$line")
        done <<<"$raw"
    fi
    if [ "${#lines[@]}" -eq 0 ]; then
        lines=("(no recent output)")
    fi
    liku_tui_set_detail "Logs for ${agent}" "${lines[@]}"
    liku_tui_render
}
