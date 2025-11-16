#!/usr/bin/env bash

set -euo pipefail

# Retrieve tmux pane ID for a running PID
liku_terminalID_from_pid() {
    local pid="$1"
    tmux list-panes -a -F "#{pane_id} #{pane_pid}" | grep " ${pid}$" | awk '{print $1}'
}
