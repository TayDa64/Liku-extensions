#!/usr/bin/env bash

set -euo pipefail

liku_tui_setup_signals() {
    trap "clear; exit" INT TERM
}
