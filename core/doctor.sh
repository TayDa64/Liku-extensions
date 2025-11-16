#!/usr/bin/env bash
set -euo pipefail

LIKUDIR="${HOME}/.liku"
STATUS_FAIL=0

print_header() {
    printf '\n== %s ==\n' "$1"
}

ok() {
    printf '[ OK ] %s\n' "$1"
}

warn() {
    printf '[WARN] %s\n' "$1"
}

fail() {
    printf '[FAIL] %s\n' "$1"
    STATUS_FAIL=$((STATUS_FAIL + 1))
}

check_install_root() {
    print_header "Install Root"
    if [ -d "$LIKUDIR" ]; then
        ok "Found ${LIKUDIR}"
    else
        fail "Install directory ${LIKUDIR} missing. Run ./install.sh"
    fi
}

check_command() {
    local name="$1"
    local remediation="$2"
    local severity="$3"

    if command -v "$name" >/dev/null 2>&1; then
        ok "$name available"
    else
        if [ "$severity" = "fail" ]; then
            fail "$name missing. ${remediation}"
        else
            warn "$name missing. ${remediation}"
        fi
    fi
}

check_inotify() {
    print_header "Dependencies"
    check_command "tmux" "Install tmux (e.g., sudo apt install tmux)" "fail"
    check_command "inotifywait" "Install inotify-tools (e.g., sudo apt install inotify-tools)" "warn"
    check_command "sqlite3" "Install sqlite3 (e.g., sudo apt install sqlite3)" "warn"
    check_command "node" "Install Node.js 20+" "warn"
    check_command "python3" "Install Python 3.11+" "warn"
}

check_wsl() {
    print_header "Platform"
    local uname_out
    uname_out="$(uname -a)"
    if grep -qi microsoft /proc/version 2>/dev/null; then
        ok "Running inside WSL"
        if [[ "$HOME" != /home/* ]]; then
            warn "WSL home path appears to be Windows FS (${HOME}). Consider running inside /home for performance."
        fi
    else
        ok "Kernel: ${uname_out%% *}"
    fi
}

check_crlf() {
    print_header "Line Endings"
    if [ ! -d "$LIKUDIR" ]; then
        warn "Skipping CRLF check because ${LIKUDIR} is missing"
        return
    fi

    local offenders=()
    while IFS= read -r -d '' file; do
        if LC_ALL=C grep -q $'\r' "$file"; then
            offenders+=("$file")
        fi
    done < <(find "$LIKUDIR" -type f -name '*.sh' -print0 2>/dev/null)

    if [ ${#offenders[@]} -eq 0 ]; then
        ok "No CRLF endings detected in ~/.liku shell scripts"
    else
        fail "Found CRLF line endings in ${#offenders[@]} files (example: ${offenders[0]}). Run: find ~/.liku -name '*.sh' -print0 | xargs -0 perl -0pi -e 's/\\r\\n/\\n/g'"
    fi
}

check_agent_state() {
    print_header "State"
    local agents_dir="${LIKUDIR}/state/agents"
    if [ -d "$agents_dir" ]; then
        if compgen -G "${agents_dir}/*.json" >/dev/null; then
            ok "Agent metadata present under ${agents_dir}"
        else
            warn "No agent metadata yet. Spawn an agent with 'liku spawn build-agent'"
        fi
    else
        warn "${agents_dir} missing. It will be created after the first agent spawn."
    fi
}

main() {
    check_install_root
    check_inotify
    check_wsl
    check_crlf
    check_agent_state

    if [ "$STATUS_FAIL" -gt 0 ]; then
        printf '\nDoctor finished with %s failure(s).\n' "$STATUS_FAIL"
        exit 1
    fi
    printf '\nDoctor finished with no blocking issues.\n'
}

main "$@"
