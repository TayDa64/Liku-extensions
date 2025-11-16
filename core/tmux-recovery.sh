#!/usr/bin/env bash
# Fault-tolerant tmux session recovery with event emission

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE_DIR="${HOME}/.liku/core"

# shellcheck disable=SC1091
if [ -f "${CORE_DIR}/event-bus.sh" ]; then
    source "${CORE_DIR}/event-bus.sh"
fi

RECOVERY_LOG="${HOME}/.liku/logs/tmux-recovery.log"
mkdir -p "$(dirname "$RECOVERY_LOG")"

EXPECTED_SESSION="${LIKU_SESSION:-$(whoami)-liku}"

liku_recovery_scan_orphans() {
    # Find dead panes across all tmux sessions
    if ! tmux list-sessions >/dev/null 2>&1; then
        return 0
    fi
    
    tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} #{pane_id} #{pane_dead}' \
        | awk '$3=="1" {print $1, $2}'
}

liku_recovery_scan_zombie_sessions() {
    # Find sessions with no live panes
    if ! tmux list-sessions >/dev/null 2>&1; then
        return 0
    fi
    
    tmux list-sessions -F '#{session_name}' | while read -r session; do
        local live_panes
        live_panes=$(tmux list-panes -t "$session" -F '#{pane_dead}' 2>/dev/null \
            | grep -c '^0$' || true)
        
        if [ "$live_panes" -eq 0 ]; then
            echo "$session"
        fi
    done
}

liku_recovery_restart_orphan() {
    local terminal_id="$1"
    local pane_id="$2"
    
    # Extract session, window, pane from terminal_id
    local session="${terminal_id%%:*}"
    local window_pane="${terminal_id#*:}"
    local window="${window_pane%%.*}"
    
    # Log the orphan detection
    local log_entry
    log_entry=$(python3 - "$terminal_id" "$pane_id" <<'PY'
import json, sys
from datetime import datetime

data = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "event": "tmux.orphan.detected",
    "terminal_id": sys.argv[1],
    "pane_id": sys.argv[2]
}
print(json.dumps(data))
PY
    )
    echo "$log_entry" >> "$RECOVERY_LOG"
    
    # Kill the dead pane
    tmux kill-pane -t "$pane_id" 2>/dev/null || true
    
    # Create a new window in the expected session
    if tmux has-session -t "$EXPECTED_SESSION" 2>/dev/null; then
        local new_pane
        new_pane=$(tmux new-window -P -F '#{pane_id}' -t "$EXPECTED_SESSION" -n "recovered-$window" 2>/dev/null || true)
        
        if [ -n "$new_pane" ]; then
            # Emit recovery event
            local payload
            payload=$(python3 - "$terminal_id" "$pane_id" "$new_pane" <<'PY'
import json, sys

data = {
    "original_terminal": sys.argv[1],
    "dead_pane": sys.argv[2],
    "new_pane": sys.argv[3],
    "action": "recreated"
}
print(json.dumps(data))
PY
            )
            
            if command -v liku_event_emit >/dev/null 2>&1; then
                liku_event_emit "system.recovered.pane" "$payload"
            fi
            
            echo "$payload" >> "$RECOVERY_LOG"
        fi
    else
        echo "Warning: Expected session '$EXPECTED_SESSION' does not exist" >&2
    fi
}

liku_recovery_cleanup_zombie_session() {
    local session="$1"
    
    # Log the zombie session
    local log_entry
    log_entry=$(python3 - "$session" <<'PY'
import json, sys
from datetime import datetime

data = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "event": "tmux.zombie.detected",
    "session": sys.argv[1]
}
print(json.dumps(data))
PY
    )
    echo "$log_entry" >> "$RECOVERY_LOG"
    
    # Kill the zombie session
    if tmux kill-session -t "$session" 2>/dev/null; then
        # Emit recovery event
        local payload
        payload=$(python3 - "$session" <<'PY'
import json, sys

data = {
    "session": sys.argv[1],
    "action": "killed_zombie"
}
print(json.dumps(data))
PY
        )
        
        if command -v liku_event_emit >/dev/null 2>&1; then
            liku_event_emit "system.recovered.session" "$payload"
        fi
        
        echo "$payload" >> "$RECOVERY_LOG"
    fi
}

liku_recovery_ensure_base_session() {
    # Ensure the base LIKU session exists with required windows
    if ! tmux has-session -t "$EXPECTED_SESSION" 2>/dev/null; then
        tmux new-session -d -s "$EXPECTED_SESSION" -n "general"
        
        # Create standard windows
        for window in background logging sandbox; do
            tmux new-window -t "$EXPECTED_SESSION" -n "$window"
        done
        
        # Emit creation event
        local payload
        payload=$(python3 - "$EXPECTED_SESSION" <<'PY'
import json, sys

data = {
    "session": sys.argv[1],
    "action": "created_base_session",
    "windows": ["general", "background", "logging", "sandbox"]
}
print(json.dumps(data))
PY
        )
        
        if command -v liku_event_emit >/dev/null 2>&1; then
            liku_event_emit "system.recovered.session" "$payload"
        fi
        
        echo "$payload" >> "$RECOVERY_LOG"
    fi
}

liku_recovery_run() {
    local orphan_count=0
    local zombie_count=0
    
    # Ensure base session exists
    liku_recovery_ensure_base_session
    
    # Scan for orphaned panes
    local orphans
    mapfile -t orphans < <(liku_recovery_scan_orphans)
    
    if [ "${#orphans[@]}" -gt 0 ]; then
        for orphan_line in "${orphans[@]}"; do
            [ -z "$orphan_line" ] && continue
            
            read -r terminal_id pane_id <<<"$orphan_line"
            echo "Recovering orphaned pane: $terminal_id ($pane_id)"
            liku_recovery_restart_orphan "$terminal_id" "$pane_id"
            ((orphan_count++))
        done
    fi
    
    # Scan for zombie sessions
    local zombies
    mapfile -t zombies < <(liku_recovery_scan_zombie_sessions)
    
    if [ "${#zombies[@]}" -gt 0 ]; then
        for zombie in "${zombies[@]}"; do
            [ -z "$zombie" ] && continue
            [ "$zombie" = "$EXPECTED_SESSION" ] && continue  # Don't kill our own session
            
            echo "Cleaning up zombie session: $zombie"
            liku_recovery_cleanup_zombie_session "$zombie"
            ((zombie_count++))
        done
    fi
    
    # Output summary
    python3 - "$orphan_count" "$zombie_count" <<'PY'
import json, sys

orphans = int(sys.argv[1])
zombies = int(sys.argv[2])

result = {
    "status": "clean" if (orphans == 0 and zombies == 0) else "recovered",
    "orphaned_panes": orphans,
    "zombie_sessions": zombies
}

print(json.dumps(result, indent=2))
PY
}

liku_recovery_show_log() {
    if [ ! -f "$RECOVERY_LOG" ]; then
        echo "No recovery log found at $RECOVERY_LOG"
        return
    fi
    
    local lines="${1:-20}"
    echo "=== Last $lines recovery events ==="
    tail -n "$lines" "$RECOVERY_LOG" | while IFS= read -r line; do
        echo "$line" | python3 -m json.tool 2>/dev/null || echo "$line"
    done
}

# CLI interface
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    cmd="${1:-run}"
    shift || true
    
    case "$cmd" in
        run)
            liku_recovery_run "$@"
            ;;
        scan)
            echo "Orphaned panes:"
            liku_recovery_scan_orphans
            echo ""
            echo "Zombie sessions:"
            liku_recovery_scan_zombie_sessions
            ;;
        log)
            liku_recovery_show_log "$@"
            ;;
        *)
            cat <<'USAGE'
Usage:
  tmux-recovery.sh run              # Run full recovery process
  tmux-recovery.sh scan             # Scan for issues without fixing
  tmux-recovery.sh log [lines]      # Show recovery log (default: 20 lines)
USAGE
            ;;
    esac
fi
