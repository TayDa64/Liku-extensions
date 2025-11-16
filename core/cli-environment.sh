#!/usr/bin/env bash

set -euo pipefail

# Utility helpers that detect the current CLI/TUI environment so LIKU can
# consistently spawn agents and render TUIs alongside the operator.

liku_cli_current_tty() {
    if tty >/dev/null 2>&1; then
        tty
    else
        printf 'unknown'
    fi
}

liku_cli_shell() {
    if [ -n "${SHELL:-}" ]; then
        printf '%s' "$SHELL"
    else
        printf 'unknown'
    fi
}

liku_cli_term() {
    if [ -n "${TERM:-}" ]; then
        printf '%s' "$TERM"
    else
        printf 'unknown'
    fi
}

liku_cli_is_tmux() {
    [[ -n "${TMUX:-}" ]]
}

liku_cli_tmux_session() {
    if liku_cli_is_tmux && command -v tmux >/dev/null 2>&1; then
        tmux display-message -p '#S' 2>/dev/null || true
    else
        printf ''
    fi
}

liku_cli_tmux_client() {
    if liku_cli_is_tmux && command -v tmux >/dev/null 2>&1; then
        tmux display-message -p '#{client_name}' 2>/dev/null || true
    else
        printf ''
    fi
}

liku_cli_is_wsl() {
    if grep -qi microsoft /proc/version 2>/dev/null; then
        return 0
    fi
    return 1
}

liku_cli_sanitize() {
    # Replace every non-alphanumeric character with an underscore so tmux accepts the name.
    printf '%s' "$1" | tr -c '[:alnum:]' '_'
}

liku_cli_session_key() {
    local tty
    tty="$(liku_cli_current_tty)"
    local user
    user="$(whoami 2>/dev/null || printf 'user')"
    local host
    host="$(hostname -s 2>/dev/null || hostname 2>/dev/null || printf 'host')"
    local raw="${user}-${host}-${tty}"
    printf 'liku-%s' "$(liku_cli_sanitize "$raw")"
}

liku_cli_target_session_name() {
    local current_session
    current_session="$(liku_cli_tmux_session)"
    if [ -n "$current_session" ]; then
        printf '%s' "$current_session"
        return
    fi
    liku_cli_session_key
}

liku_cli_capture_environment() {
    local tty term shell tmux_session tmux_client session_key is_tmux is_wsl
    tty="$(liku_cli_current_tty)"
    term="$(liku_cli_term)"
    shell="$(liku_cli_shell)"
    tmux_session="$(liku_cli_tmux_session)"
    tmux_client="$(liku_cli_tmux_client)"
    session_key="$(liku_cli_session_key)"
    if liku_cli_is_tmux; then
        is_tmux=true
    else
        is_tmux=false
    fi
    if liku_cli_is_wsl; then
        is_wsl=true
    else
        is_wsl=false
    fi

    local state_dir="${HOME}/.liku/state/session"
    mkdir -p "$state_dir"
    cat > "${state_dir}/env.json" <<EOF
{
  "term": "${term}",
  "shell": "${shell}",
  "tty": "${tty}",
  "tmux_session": "${tmux_session}",
  "tmux_client": "${tmux_client}",
  "session_key": "${session_key}",
  "is_tmux": ${is_tmux},
  "is_wsl": ${is_wsl},
  "timestamp": "$(date -Iseconds)"
}
EOF
}

liku_cli_supports_tui() {
    local term
    term="$(liku_cli_term)"
    if [ "$term" = "dumb" ] || [ "$term" = "unknown" ]; then
        return 1
    fi
    if ! command -v tput >/dev/null 2>&1; then
        return 1
    fi
    tput cols >/dev/null 2>&1 && tput lines >/dev/null 2>&1
}

liku_cli_env_summary() {
    local tty term session
    tty="$(liku_cli_current_tty)"
    term="$(liku_cli_term)"
    session="$(liku_cli_target_session_name)"
    printf 'TERM=%s | TTY=%s | Session=%s\n' "$term" "$tty" "$session"
}

liku_cli_require_tmux() {
    if ! command -v tmux >/dev/null 2>&1; then
        printf '[Liku] tmux is required. Install tmux before spawning agents.\n' >&2
        exit 1
    fi
}

liku_cli_ensure_tmux_session() {
    local session_name="$1"
    if tmux has-session -t "$session_name" 2>/dev/null; then
        return 0
    fi
    local cols lines
    cols=$(tput cols 2>/dev/null || printf '120')
    lines=$(tput lines 2>/dev/null || printf '32')
    tmux new-session -d -s "$session_name" -x "$cols" -y "$lines"
}
