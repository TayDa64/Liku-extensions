#!/usr/bin/env bash

set -euo pipefail

liku_tui_render() {
    clear
    printf 'LIKU Bookkeeper\n'
    liku_tui_render_agents
}
