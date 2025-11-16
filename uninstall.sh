#!/usr/bin/env bash
set -euo pipefail

PREFIX="${HOME}/.liku"
rm -rf "${PREFIX}"

echo "[Liku] Uninstalled. Guidance logs remain under logs/guidance if present."
