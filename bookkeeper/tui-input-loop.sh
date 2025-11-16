#!/usr/bin/env bash

set -euo pipefail

liku_tui_input_loop() {
    while read -rsn1 key; do
        case "$key" in
            R) liku_key_R ;;
            K) liku_key_K ;;
            G) liku_key_G ;;
            q|Q) break ;;
        esac
    done
}
