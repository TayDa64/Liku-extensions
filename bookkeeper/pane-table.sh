#!/usr/bin/env bash

set -euo pipefail

LIKUBOOK_PANE_DIR="${HOME}/.liku/state/panes"
declare -a LIKUBOOK_PANE_ROWS=()

liku_pane_collect_rows() {
    LIKUBOOK_PANE_ROWS=()
    if [ ! -d "$LIKUBOOK_PANE_DIR" ] || ! compgen -G "${LIKUBOOK_PANE_DIR}"'/pane-*.json' >/dev/null; then
        return
    fi
    local file
    for file in $(ls -1t "${LIKUBOOK_PANE_DIR}"/pane-*.json 2>/dev/null || true); do
        [ -e "$file" ] || continue
        local data
        data=$(python3 - "$file" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text())
print('\u0001'.join([
    data.get('terminal_id', '?'),
    data.get('status', '?'),
    data.get('label') or data.get('window_name', ''),
    data.get('last_command', ''),
    data.get('timestamp', ''),
]))
PY
        )
        LIKUBOOK_PANE_ROWS+=("$data")
    done
}

liku_tui_render_panes() {
    liku_pane_collect_rows
    printf '\n TMUX Activity\n'
    printf ' %-32s %-8s %-12s %-24s %s\n' 'TERMINAL ID' 'STATUS' 'LABEL' 'LAST COMMAND' 'UPDATED'
    if [ "${#LIKUBOOK_PANE_ROWS[@]}" -eq 0 ]; then
        printf ' (no tmux-agent executions yet; run "liku exec -- <cmd>" to populate)\n'
        return
    fi
    local row terminal status label cmd ts
    for row in "${LIKUBOOK_PANE_ROWS[@]}"; do
        IFS=$'\x01' read -r terminal status label cmd ts <<<"$row"
        if [ "${#cmd}" -gt 24 ]; then
            cmd="${cmd:0:23}…"
        fi
        printf ' %-32s %-8s %-12s %-24s %s\n' "$terminal" "$status" "${label:-general}" "$cmd" "$ts"
    done
}
