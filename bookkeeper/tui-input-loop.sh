#!/usr/bin/env bash

set -euo pipefail

liku_tui_input_loop() {
    while IFS= read -rsn1 key; do
        case "$key" in
            R) liku_key_R ;;
            K) liku_key_K ;;
            G) liku_key_G ;;
            D) liku_key_D ;;
            L) liku_key_L ;;
            A) liku_key_A ;;
            P) liku_key_P ;;
            C) liku_key_C ;;
            S) liku_key_S ;;
            W) liku_key_W ;;
            q|Q) break ;;
            $'\e') liku_tui_handle_escape ;;
        esac
    done
}

liku_tui_handle_escape() {
    local next
    if ! IFS= read -rsn1 next; then
        return
    fi
    if [ "$next" != "[" ]; then
        return
    fi
    if ! IFS= read -rsn1 next; then
        return
    fi
    case "$next" in
        A) liku_key_up ;;
        B) liku_key_down ;;
    esac
}
