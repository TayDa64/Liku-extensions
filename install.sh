#!/usr/bin/env bash
set -euo pipefail

PREFIX="${HOME}/.liku"

mkdir -p "${PREFIX}/bin"
mkdir -p "${PREFIX}/state"
mkdir -p "${PREFIX}/logs"
mkdir -p "${PREFIX}/sessions"

cp -r bin/*        "${PREFIX}/bin/"
cp -r core         "${PREFIX}/"
cp -r agents       "${PREFIX}/"
cp -r config       "${PREFIX}/"
cp -r bookkeeper   "${PREFIX}/"

if ! grep -q 'LIKUPATH' "${HOME}/.bashrc" 2>/dev/null; then
    echo 'export PATH="$PATH:'"${PREFIX}/bin"'" >> "${HOME}/.bashrc"
fi

echo "[Liku] Installed successfully."
