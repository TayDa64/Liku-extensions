# LIKU

**Wisdom for Terminals.** Liku is a terminal-native multi-agent orchestration framework that coordinates tmux-based subagents, a Bookkeeper TUI, and an auditable event bus. Everything runs from the CLI (or WSL on Windows) to keep approvals, telemetry, and remediation trails transparent.

## Why LIKU

- **Terminal orchestrator:** `core/runtime.sh` tracks TerminalIDs, PID/PGID/SID data, and tmux panes for every subagent.
- **Bookkeeper TUI:** A curses-style dashboard (see `bookkeeper/*.sh`) that shows active agents, hotkeys, and conversational guidance controls.
- **Event bus:** Append-only JSONL logs under `state/events/` drive auditing, remediation summaries, and future plugin integrations.
- **Guidance memory:** Conversations persist as JSON files under `logs/guidance/` and are only removed when the operator explicitly deletes them.
- **CLI-first safety:** Installer, approvals, and telemetry mirror UX patterns from VS Code Workspace Trust, Claude Code permissions, Gemini Agent Mode, and OpenAI Codex CLI.
- **Session awareness:** `core/cli-environment.sh` captures `TERM`, `TTY`, `TMUX`, and WSL data so LIKU always spawns agents and renders TUIs inside the same environment the operator is using.

## Architecture Snapshot

| Pillar | Responsibilities | Source |
| --- | --- | --- |
| Terminal Orchestrator | tmux pane lifecycle, TerminalID allocation, PID/PGID/SID enforcement | `core/runtime.sh`, `core/pid-tools.sh`, `core/terminalID.sh` |
| Context Store | SQLite + JSONL metadata for agents, approvals, and summaries | `core/context-store.sh`, `state/sessions/*` |
| Event Bus | JSONL streaming, remediation capture, approval hooks | `core/event-bus.sh`, `docs/event-bus.md` |
| Bookkeeper | TUI hotkeys, conversational guidance, approval surface | `bookkeeper/*.sh`, `docs/bookkeeper.md` |
| Safety Guards | Approval states, HTTP gating, process cleanup | `core/safety-guards.sh`, `docs/protocol.md` |

See `docs/architecture.md` for the full blueprint and `docs/foundation-plan.md` for the phase roadmap.

## Repository Layout

| Path | Description |
| --- | --- |
| `bin/` | CLI entrypoints (`liku`, `liku-bookkeeper`, `liku-eventd`, etc.). |
| `core/` | Runtime shell scripts (orchestrator, event bus, state machine, PID tools). |
| `core/cli-environment.sh` | Detects the active terminal/TMUX/WSL context and enforces tmux session reuse. |
| `bookkeeper/` | TUI layout, input loops, and hotkey handlers. |
| `agents/` | Sample build/test/lint agents plus reusable templates. |
| `config/` | YAML stubs for agents, paths, and runtime defaults. |
| `state/` | Session databases, agent metadata, and event streams. |
| `logs/guidance/` | Long-lived conversational guidance archives. |
| `docs/` | Architecture, protocol, installation, rubric, and PR templates. |

## Requirements

- POSIX shell (bash/zsh)
- `tmux`, `inotifywait`, `sqlite3`
- Node.js 20+ (agent tooling)
- Python 3.11+ (optional helpers)
- Git

### Windows Support (WSL Only)

1. Enable WSL: `wsl --install -d Ubuntu`
2. Run all commands from the Ubuntu shell.
3. Do **not** execute installers directly from PowerShell/CMD.

## CLI/TUI Awareness

- Every CLI entrypoint runs `core/cli-environment.sh`, which snapshots the active shell, terminal type, tty path, tmux session, and WSL detection into `~/.liku/state/session/env.json`.
- `liku spawn <agent>` now reuses the tmux session that matches your current terminal (if you are already inside tmux it splits the existing pane; otherwise it creates/reuses a session derived from your TTY).
- Bookkeeper refuses to start in `TERM=dumb` shells and displays a banner such as `TERM=xterm-256color | TTY=/dev/pts/3 | Session=liku-user-host-dev_pts_3` to prove which interface it is targeting.
- Agent state files under `state/agents/<name>.json` include the detected `term`, `tty`, and session name so you can audit where each subprocess lives.
- Event payloads emitted on `agent.spawn` include the same metadata, making it easy to stream the audit trail or debug mismatched sessions.

## Installation

```bash
git clone <repo-url> liku
cd liku
chmod +x install.sh uninstall.sh
./install.sh
```

The installer copies runtime files to `~/.liku`, places binaries in `~/.liku/bin`, and appends the PATH export snippet to `.bashrc` if it is missing. Re-run `./install.sh` after pulling new changes to update the local runtime.

### Uninstall

```bash
./uninstall.sh
```

`uninstall.sh` removes `~/.liku` but intentionally leaves `logs/guidance` and `/agents/<id>/commands` so you can archive them manually.

## Post-Install Checklist

```bash
liku status          # lists managed agents
liku bookkeeper      # launches the TUI inside the current terminal
liku event stream    # tails JSONL events once event tooling is wired
```

- Ensure `tmux` is running and accessible from the current shell.
- Review `config/liku.yaml` and `config/agents.yaml` to confirm agent names, default paths, and upcoming approval policies.
- For Windows users, open a new WSL terminal (so PATH updates from `.bashrc` are picked up) before launching `liku`.

## Working with Agents

Agents live under `agents/<name>/` and are defined by `agent.json` + shell handlers. Use the CLI to start them inside dedicated tmux panes:

```bash
liku spawn build-agent
liku spawn test-agent
liku spawn lint-agent
```

- Metadata for each agent is stored under `state/agents/<name>.json` and includes TerminalID, PID, PGID, and SID.
- Error output containing `ERROR|FAIL|Exception|Traceback` automatically triggers remediation summaries under `/agents/<name>/commands/YYYYMMDD.jsonl` per `docs/event-bus.md`.

## Bookkeeper Guidance Workflow

Bookkeeper acts as the operator’s co-pilot:

1. **Monitor:** Hotkeys (see `docs/bookkeeper.md`) refresh tables, terminate agents, or open the guidance pane.
2. **Converse:** Ask “List guidance files” to display every JSON archive with ID, session, size, and timestamps.
3. **Retain:** Guidance logs (`logs/guidance/*.json`) persist until *you* remove them. Bookkeeper never deletes data—when you say “Remove guidance #n,” it confirms the path and suggests the manual command:

    ```bash
    rm logs/guidance/guidance-2025-11-16.json
    ```

4. **Approve:** Approval modes (`auto`, `ask`, `deny`, `plan-review`) follow the protocol described in `docs/protocol.md`. Configure your default mode in `config/liku.yaml` (or the future SQLite store) before enabling HTTP or plugin surfaces.

## Event Streaming & Auditing

- Daily JSONL files sit under `state/events/` and can be tailed with `liku event stream --since 5m | jq '.'` once the CLI event helper (`liku-eventd`) is wired in.
- Guidance actions emit `guidance.append|guidance.list|guidance.delete.requested` events for auditability.
- Remediation summaries are mirrored into `/agents/<id>/commands/DATE.jsonl` using the sentence template documented in `docs/event-bus.md`.

Before exposing HTTP callbacks or external plugins, run:

```bash
liku event stream --since 5m
```

and verify events populate in real time.

## Configuration & Customization

- **Agents:** Update `config/agents.yaml` to register or remove agent names.
- **Paths:** `config/paths.yaml` controls the default runtime root (`~/.liku`).
- **Approvals & Guidance Defaults:** Until the SQLite context store is fully implemented, keep provisional settings inside `config/liku.yaml` or a custom JSON file under `~/.liku/config/` (see `docs/installation.md`).

## Continuous Monitoring

The `.github/workflows/yolo-supervisor.yml` workflow mirrors the “YOLO Supervisor” checklist to ensure every PR labeled `yolo` kicks off monitoring runs. Refer to `docs/foundation-pr-checklist.md` before opening a PR so coding agents and the Bookkeeper TUI stay in sync.

## Troubleshooting

- **`liku` not found:** Open a new shell session or manually add `export PATH="$PATH:$HOME/.liku/bin"` to `.bashrc`.
- **tmux errors:** Confirm `tmux` is installed (`tmux -V`) and accessible from WSL if you’re on Windows.
- **Bookkeeper blank screen:** Ensure `$TERM` supports curses (e.g., `xterm-256color`) and that `bookkeeper/*.sh` files remain executable.
- **Missing dependencies:** Install `inotifywait` (`sudo apt install inotify-tools`) and `sqlite3` before spawning agents.
- **Guidance files piling up:** Use Bookkeeper’s listing flow to identify old files, then manually delete them with `rm logs/guidance/<file>.json`.

## Additional Documentation

- `docs/architecture.md` – Detailed runtime pillars and roadmap.
- `docs/event-bus.md` – JSONL schema, CLI streaming, and remediation logging.
- `docs/bookkeeper.md` – TUI behavior, hotkeys, and guidance UX.
- `docs/protocol.md` – Approval modes, lifecycle states, and compliance checklist.
- `docs/installation.md` – Full prerequisite list and WSL instructions.
- `docs/rubric.md` – Production readiness scoring.
- `docs/foundation-plan.md` / `docs/foundation-pr-checklist.md` / `docs/foundation-pr-draft.md` – Planning artifacts for upcoming phases.

With the scaffold in place, you can iterate on agents, approvals, and guidance memory while keeping every action auditable from the terminal.
