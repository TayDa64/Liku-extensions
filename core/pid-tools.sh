#!/usr/bin/env bash

set -euo pipefail

liku_get_pgid() {
    ps -o pgid= "$1" | tr -d ' '
}

liku_get_sid() {
    ps -o sid= "$1" | tr -d ' '
}

liku_is_process_running() {
    kill -0 "$1" 2>/dev/null
}
