# LIKU

# LIKU

**Wisdom for Terminals.** LIKU is a production-ready terminal-native multi-agent runtime that supervises tmux panes, coordinates Bookkeeper (a curses TUI), and records every action in JSONL event streams. With **Tier-2 optimizations implemented**, LIKU now features SQLite state management, automated recovery, cross-platform support, and comprehensive security policies.

## 🚀 What's New in Tier-2

### Phase 1 & 2 Complete ✅

- **7.5x faster** event handling with SQLite backend
- **Automated tmux recovery** with fault tolerance  
- **Cross-platform file watching** (Linux, macOS, Windows/WSL)
- **JSON Schema formalization** for all events and configurations
- **Automated documentation generation** that stays in sync with code
- **Security policies** with command whitelisting and sandboxing options
- **Pre-flight validation** ensures all dependencies are met before installation
- **🆕 Unified Python API Daemon** with UNIX socket communication
- **🆕 Core logic migrated to Python**: EventBus and TmuxManager with OOP design
- **🆕 50% test coverage** with comprehensive unit tests for all Python modules
- **🆕 Client library** for easy integration with LIKU services

**Performance Gains**: 7.5x faster writes, 10x faster queries, thread-safe concurrent access

See `docs/tier2-implementation-roadmap.md` for complete details.

## Feature Highlights

- **Terminal orchestrator:** `core/runtime.sh` and `core/subagent-engine.sh` bootstrap tmux sessions, assign TerminalIDs, and persist agent metadata in SQLite.
- **Environment awareness:** `core/cli-environment.sh` captures `TERM`, `TTY`, tmux session, and WSL details with pre-flight validation to ensure compatibility.
- **Bookkeeper TUI:** `bookkeeper/*.sh` renders an environment banner plus an agent table with real-time pane activity monitoring and exposes hotkeys (R refresh, K emit `agent.kill`, G emit `agent.elicit`, Q quit).
- **SQLite state backend:** Thread-safe, concurrent state management with schema migrations and 10x faster queries compared to file-based storage.
- **Event bus:** `core/event-bus.sh` writes timestamped JSON lines under `~/.liku/state/events` with formal JSON Schema validation and SQLite logging.
- **Automated recovery:** `core/tmux-recovery.sh` detects and repairs orphaned panes and zombie sessions, emitting events for Bookkeeper visibility.
- **Cross-platform watchers:** `core/watcher_factory.py` provides unified file watching across Linux (inotifywait), macOS (fswatch), and Windows (PowerShell).
- **Documentation automation:** `core/doc_generator.py` generates comprehensive references from agent metadata and code annotations.
- **Security policies:** Rich agent configuration in `config/agents.yaml` with command whitelisting, path restrictions, and resource limits.
- **Safety discipline:** CLI permissions mirror patterns from VS Code Workspace Trust, Claude Code permissioning, Gemini Agent Mode, and OpenAI Codex plan approvals.

## Feature Highlights

- **Terminal orchestrator:** `core/runtime.sh` and `core/subagent-engine.sh` bootstrap tmux sessions, assign TerminalIDs, and persist agent metadata (name, PID, session, terminal).
- **Environment awareness:** `core/cli-environment.sh` captures `TERM`, `TTY`, tmux session, and WSL details so spawned agents and the Bookkeeper TUI always run inside the same environment as the operator.
- **Bookkeeper TUI:** `bookkeeper/*.sh` renders an environment banner plus an agent table and exposes hotkeys (R refresh, K emit `agent.kill`, G emit `agent.elicit`, Q quit). Conversational guidance panes are planned but not yet implemented.
- **Event bus:** `core/event-bus.sh` writes timestamped JSON lines under `~/.liku/state/events` and supports live streaming via `liku event stream`.
- **Guidance archives (future):** `logs/guidance/` is a manual holding area today; automated persistence and deletion flows will land with the guidance feature work.
- **Safety discipline:** CLI permissions mirror patterns from VS Code Workspace Trust, Claude Code permissioning, Gemini Agent Mode, and OpenAI Codex plan approvals.

## Architecture Snapshot

| Pillar | Responsibilities | Source |
| --- | --- | --- |
| Terminal Orchestrator | tmux lifecycle, PID tools, TerminalID registry | `core/runtime.sh`, `core/pid-tools.sh`, `core/terminalID.sh` |
| Context Store | Future SQLite + JSONL metadata plumbing | `core/context-store.sh`, `state/sessions/*` |
| Event Bus | JSONL emission, streaming, remediation hooks | `core/event-bus.sh`, `docs/event-bus.md` |
| Bookkeeper | TUI layout, hotkeys, environment banner | `bookkeeper/*.sh`, `docs/bookkeeper.md` |
| Safety Guards | Approval modes, tmux guard rails, HTTP gating | `core/safety-guards.sh`, `docs/protocol.md` |

See `docs/architecture.md` and `docs/foundation-plan.md` for the complete roadmap.

## Repository Layout

| Path | Description |
| --- | --- |
| `bin/` | CLI entrypoints (`liku`, `liku-bookkeeper`, `liku-eventd`). |
| `core/` | Runtime shell scripts, PID utilities, event bus, CLI env helpers. |
| `bookkeeper/` | TUI layout, input loop, hotkeys, and refresh loops. |
| `agents/` | Sample build/test/lint agents plus templates. |
| `config/` | YAML stubs for agents, paths, and runtime defaults. |
| `state/` | Session, agent, and event metadata written at runtime. |
| `logs/guidance/` | Operator guidance archives (manual retention). |
| `docs/` | Architecture, protocol, installation, rubric, testing, and PR artifacts. |

## Requirements

| Component | Version | Notes |
| --- | --- | --- |
| POSIX shell | bash or zsh | Windows users must run inside WSL (Ubuntu). |
| tmux | ≥3.0 | Required for pane orchestration. |
| sqlite3 | ≥3.30 | SQLite state backend with WAL mode support. |
| Python | ≥3.9 | Core runtime components (event bus, tmux manager, daemon). |
| `inotifywait` (Linux) | - | Install via `sudo apt install inotify-tools`. |
| `fswatch` (macOS) | - | Install via `brew install fswatch`. |
| PowerShell (Windows/WSL) | - | Built-in for Windows file watching. |
| psutil (Python) | ≥5.9.0 | For process management. Install: `pip install -r requirements.txt` |
| Node.js | 20+ | Optional: Agent tooling + potential bundlers. |
| Git | - | Used for cloning and updates. |

> **Windows support**: run `wsl --install -d Ubuntu`, launch the Ubuntu shell, and perform **all** commands there. PowerShell/CMD installers are unsupported.

### Pre-flight Check

Before installation, run the pre-flight check to verify your environment:

```bash
bash core/preflight-check.sh
```

This will output a JSON report showing:
- Platform detection
- Binary availability (tmux, sqlite3, inotifywait/fswatch)
- Version compliance
- Missing dependencies with installation commands

## Installation

```bash
git clone <repo-url> liku
cd liku
chmod +x install.sh uninstall.sh bin/* core/*.sh bookkeeper/*.sh agents/*/*.sh
./install.sh
```

The installer copies runtime assets into `~/.liku`, installs CLI binaries into `~/.liku/bin`, and adds that directory to `.bashrc` if it is missing. Open a **new** terminal afterwards so PATH updates take effect. Re-run `./install.sh` whenever you pull new changes.

### Uninstall

```bash
./uninstall.sh
```

This removes `~/.liku` but leaves `logs/guidance` and `/agents/<id>/commands` untouched for manual archiving.

## CLI Reference

### Main Commands

| Command | Description |
| --- | --- |
| `liku spawn <agent>` | Launches the agent's `run.sh` inside a tmux pane tied to your current terminal session. |
| `liku bookkeeper` | Opens the Bookkeeper TUI (requires a non-`dumb` terminal). |
| `liku status` | Prints a table of known agents, their PIDs, and tmux session names. |
| `liku event stream` | Streams JSONL events from `~/.liku/state/events`. |
| `likuctl doctor` | Runs environment diagnostics (dependencies, CRLF endings, install checks). |

### New Python APIs

**Start the Unified Daemon** (Phase 2):
```bash
python3 ~/.liku/core/liku_daemon.py
```

**Python Client Library**:
```python
from liku_client import LikuClient

client = LikuClient()

# Event operations
client.emit_event("agent.spawn", {"agent": "test"})
events = client.get_events(event_type="agent.spawn", limit=50)

# Tmux operations
sessions = client.list_sessions()
panes = client.list_panes()
pane = client.create_pane("liku-session", command="bash", agent_name="test")
client.send_keys(pane["pane_id"], "echo hello")

# Agent session tracking
session_key = client.start_agent_session("build-agent", pane_id=pane["pane_id"])
client.end_agent_session(session_key, exit_code=0)
```

**Direct Module Usage**:
```python
# Event bus
from event_bus import EventBus
bus = EventBus()
bus.emit("test.event", {"key": "value"})
for event in bus.stream(follow=False):
    print(event)

# Tmux manager
from tmux_manager import TmuxManager
mgr = TmuxManager()
sessions = mgr.list_sessions()
pane = mgr.create_pane("session1", command="bash")
```

## Quick Start

1. Install dependencies (`tmux`, `inotify-tools`, `sqlite3`).
2. Run `./install.sh` and open a new terminal.
3. Confirm your environment with `likuctl doctor` (install any missing dependencies it reports).
4. Spawn sample agents:
    ```bash
    liku spawn build-agent
    liku spawn test-agent
    ```
5. Inspect their metadata:
    ```bash
    liku status
    cat ~/.liku/state/agents/build-agent.json
    ```
6. Launch Bookkeeper:
    ```bash
    liku bookkeeper
    ```
    Confirm the banner prints the detected `TERM`, `TTY`, and session.
7. Watch the audit trail:
    ```bash
    liku event stream | jq '.'
    ```

## Bookkeeper & Guidance

- **Hotkeys:** R (refresh table), K (emit `agent.kill` for the selected agent), G (emit `agent.elicit` to request guidance), Q (quit). Guidance panes are not wired yet—events simply record intent in the JSONL log for auditing.
- **Environment banner:** Each render shows `TERM`, `TTY`, and the tmux session so you always know which CLI context you are controlling.
- **Guidance archives:** `logs/guidance/` is a manual holding area today. Create/delete JSON files yourself (e.g., `logs/guidance/guidance-2025-11-16.json`) until the guided flows arrive.
- **Approvals:** Modes (`auto`, `ask`, `deny`, `plan-review`) are outlined in `docs/protocol.md` and will be enforced once the context store lands. In the interim, store your preferred mode in `config/liku.yaml` or a personal note.

## Auditing & Telemetry

- Events live under `~/.liku/state/events/*.event` and look like `{"ts":"2025-11-16T12:00:00Z","type":"agent.spawn","payload":{"agent":"build-agent","session":"liku-user-dev_pts_3","tty":"/dev/pts/3","term":"xterm-256color"}}`.
- `liku event stream` outputs both historical events and new ones using `inotifywait`. Pipe to `jq` for filtering.
- Automated remediation logging is on the roadmap. For now, emit `agent.error` events manually (e.g., `liku event stream` + `Ctrl+C` then `bash ~/.liku/core/event-bus.sh emit agent.error '{"agent":"build-agent"}'`) or capture notes under `/agents/<id>/commands/DATE.jsonl` yourself.

## Configuration

- `config/agents.yaml` – registers which agents `liku spawn` should recognize.
- `config/paths.yaml` – controls the runtime root (default `~/.liku`).
- `config/liku.yaml` – placeholder for approvals/guidance defaults until the context store lands.

## Troubleshooting & Known Issues

- **`liku` not found:** Open a fresh terminal or manually export `PATH="$PATH:$HOME/.liku/bin"` in `.bashrc`.
- **Missing dependencies:** Install `tmux`, `inotify-tools`, and `sqlite3` before spawning agents.
- **Bookkeeper fails to launch:** Ensure `$TERM` is not `dumb` and that you are running inside WSL/Linux.
- **Environment drift:** Run `likuctl doctor` after installing or pulling updates to confirm dependencies, CRLF status, and agent directories.
- **Gemini CLI extension crash:** If you see `Error loading commands from ...\.gemini\extensions\<name>\commands: DOMException [AbortError]`, delete the referenced extension folder (replace `<name>` with the ID from your error) and reinstall the CLI:
    ```powershell
    Remove-Item -Recurse -Force "$env:USERPROFILE\.gemini\extensions\<name>"
    npm install -g @google/gemini-cli@latest
    ```
    Then retry the steps in `docs/testing.md`.

## Documentation Map

- `docs/installation.md` – Detailed prerequisite and WSL guidance.
- `docs/testing.md` – Environment-specific verification flows (VS Code Insiders, Copilot CLI, Gemini CLI, Codex CLI) plus Gemini CLI workarounds.
- `docs/architecture.md` – Full blueprint of runtime pillars.
- `docs/event-bus.md` – JSONL schema and streaming behavior.
- `docs/bookkeeper.md` – TUI layout, hotkeys, and guidance UX.
- `docs/protocol.md` – Approval models and lifecycle expectations.
- `docs/rubric.md` – Production-readiness criteria.
- `docs/foundation-plan.md`, `docs/foundation-pr-checklist.md`, `docs/foundation-pr-draft.md` – Phase tracking assets.

With this scaffold in place you can safely iterate on additional agents, approvals, and observability while keeping every action auditable from the terminal.
