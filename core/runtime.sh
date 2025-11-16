#!/usr/bin/env bash
# Core runtime initializer for Liku system.
# All commands flow through this file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "${SCRIPT_DIR}/pid-tools.sh"
source "${SCRIPT_DIR}/terminalID.sh"
source "${SCRIPT_DIR}/context-store.sh"
source "${SCRIPT_DIR}/event-bus.sh"
source "${SCRIPT_DIR}/subagent-engine.sh"
source "${SCRIPT_DIR}/state-machine.sh"
source "${SCRIPT_DIR}/safety-guards.sh"
source "${SCRIPT_DIR}/cli-environment.sh"

liku_runtime_init() {
    mkdir -p "${HOME}/.liku/state"
    mkdir -p "${HOME}/.liku/logs"
    mkdir -p "${HOME}/.liku/agents"
    liku_cli_capture_environment
}
