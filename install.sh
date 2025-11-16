#!/usr/bin/env bash
set -euo pipefail

PREFIX="${HOME}/.liku"

echo "[Liku] Starting installation..."

# Run pre-flight checks
echo "[Liku] Running environment checks..."
if [ -f "./core/preflight-check.sh" ]; then
    if ! bash ./core/preflight-check.sh > "${PREFIX}/preflight-results.json" 2>&1; then
        echo "[Liku] WARNING: Pre-flight checks found issues. See ${PREFIX}/preflight-results.json for details."
        echo "[Liku] Installation will continue, but some features may not work."
    else
        echo "[Liku] Pre-flight checks passed."
    fi
fi

# Create directory structure
mkdir -p "${PREFIX}/bin"
mkdir -p "${PREFIX}/state/agents"
mkdir -p "${PREFIX}/state/events"
mkdir -p "${PREFIX}/state/panes"
mkdir -p "${PREFIX}/state/sessions"
mkdir -p "${PREFIX}/logs/guidance"
mkdir -p "${PREFIX}/logs"
mkdir -p "${PREFIX}/db"

# Copy files
echo "[Liku] Installing components..."
cp -r bin/*        "${PREFIX}/bin/"
cp -r core         "${PREFIX}/"
cp -r agents       "${PREFIX}/"
cp -r config       "${PREFIX}/"
cp -r bookkeeper   "${PREFIX}/"
cp -r schemas      "${PREFIX}/"

# Make scripts executable
chmod +x "${PREFIX}"/bin/*
chmod +x "${PREFIX}"/core/*.sh
chmod +x "${PREFIX}"/bookkeeper/*.sh

# Make Python scripts executable
if [ -f "${PREFIX}/core/watcher_factory.py" ]; then
    chmod +x "${PREFIX}/core/watcher_factory.py"
fi
if [ -f "${PREFIX}/core/state_backend.py" ]; then
    chmod +x "${PREFIX}/core/state_backend.py"
fi
if [ -f "${PREFIX}/core/doc_generator.py" ]; then
    chmod +x "${PREFIX}/core/doc_generator.py"
fi

# Initialize SQLite database
echo "[Liku] Initializing state database..."
if command -v python3 >/dev/null 2>&1; then
    python3 "${PREFIX}/core/state_backend.py" "${PREFIX}/db/liku.db" >/dev/null 2>&1 || \
        echo "[Liku] WARNING: Failed to initialize database. Some features may not work."
fi

# Generate documentation
echo "[Liku] Generating documentation..."
if command -v python3 >/dev/null 2>&1; then
    mkdir -p docs
    python3 "${PREFIX}/core/doc_generator.py" "$(pwd)" >/dev/null 2>&1 || \
        echo "[Liku] WARNING: Failed to generate documentation."
fi

# Update PATH if needed
if ! grep -q 'LIKUPATH' "${HOME}/.bashrc" 2>/dev/null; then
    {
        echo ''
        echo '# LIKU Path Configuration'
        echo "export PATH=\"\$PATH:${PREFIX}/bin\""
        echo "export LIKU_HOME=\"${PREFIX}\""
    } >> "${HOME}/.bashrc"
    echo "[Liku] Added LIKU to .bashrc. Please run: source ~/.bashrc"
fi

# Create a recovery cron job (optional)
echo "[Liku] Setting up recovery automation..."
cat > "${PREFIX}/bin/liku-recovery-cron" <<'CRON'
#!/usr/bin/env bash
# Run tmux recovery every 5 minutes
*/5 * * * * "${HOME}/.liku/core/tmux-recovery.sh" run >> "${HOME}/.liku/logs/recovery.log" 2>&1
CRON
chmod +x "${PREFIX}/bin/liku-recovery-cron"

echo ""
echo "[Liku] ✓ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Run: source ~/.bashrc"
echo "  2. Start the bookkeeper: liku bookkeeper"
echo "  3. Spawn an agent: liku spawn build-agent"
echo ""
echo "For automated recovery, add this to your crontab:"
echo "  ${PREFIX}/bin/liku-recovery-cron"
echo ""
