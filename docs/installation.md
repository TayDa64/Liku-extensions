# LIKU Installation & Setup

This guide enforces the CLI-first, POSIX-only philosophy. Windows users must install via WSL.

## 1. Prerequisites

- POSIX shell (bash/zsh)
- Node.js 20+ (for bundler/CLI tooling)
- `tmux`, `inotifywait`, `sqlite3`
- Python 3.11+ (optional for auxiliary scripts)
- Git

### Windows (WSL-only)

1. Enable WSL: `wsl --install -d Ubuntu`
2. Launch Ubuntu and run the same POSIX commands as Linux/macOS.
3. Do **not** run installers from PowerShell or CMD.

## 2. Installation Steps

```bash
# Clone
git clone <repo> liku
cd liku

# Install
./install.sh
```

`install.sh` copies binaries to `~/.liku/bin`, context files to `~/.liku/core`, and updates `PATH` in `.bashrc`.

## 3. Post-Install Configuration

```bash
# Verify
liku status

# Set approval mode before running agents
bookkeeper set approval ask

# Initialize guidance defaults
echo '{"mode":"ask"}' > ~/.liku/config/guidance.json
```

## 4. Guidance Management Commands

Use conversational prompts inside Bookkeeper:

- “List guidance files” → Bookkeeper shows table + emits `guidance.list`.
- “Remove guidance #n” → Bookkeeper confirms then suggests `rm logs/guidance/<file>.json`.

Manual deletion example:

```bash
rm logs/guidance/guidance-2025-11-16.json
```

## 5. Event Streaming

Before enabling HTTP endpoints or plugins, verify auditing:

```bash
liku event stream --since 5m | jq '.type, .payload'
```

## 6. Upgrades & Removal

```bash
# Update
git pull
./install.sh

# Uninstall
./uninstall.sh
```

`uninstall.sh` removes `~/.liku` files but leaves `logs/guidance` and `/agents/<id>/commands` untouched so the user can archive them manually.

This procedure aligns with the scaffolding in `Ideas/` while guaranteeing consistent POSIX/WSL behavior.
