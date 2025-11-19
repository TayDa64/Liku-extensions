#!/usr/bin/env bash
set -euo pipefail

# Get the directory of the currently executing script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Execute the handler script, passing all arguments to it
"$DIR/handler.sh" "$@"
