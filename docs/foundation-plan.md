# Foundation Phase PR Plan

Goal: land the baseline LIKU scaffold so subsequent phases (context store, guidance memory, approvals, telemetry) can proceed in parallel.

## 1. Branch Strategy

- Branch name suggestion: `feature/foundation-runtime`.
- PR Title: "Phase 1 – Runtime & Bookkeeper Scaffold".
- Labels: `phase:foundation`, `yolo` (for YOLO Supervisor monitoring), `needs-review`.

## 2. Scope of Work

1. **Core Runtime Files (from Ideas scaffold)**
   - `core/runtime.sh`, `pid-tools.sh`, `terminalID.sh`, `context-store.sh` (stub), `event-bus.sh`, `subagent-engine.sh`, `safety-guards.sh`, `orchestrator.sh`, `state-machine.sh`.
   - Ensure tmux session initialization, TerminalID lookup, PID/PGID/SID helpers.
2. **Binaries (`bin/`)**
   - `liku`, `liku-agent`, `liku-bookkeeper`, `liku-tmux`, `liku-daemon`, `liku-eventd` stubs invoking the core scripts.
3. **Bookkeeper TUI Skeleton**
   - `bookkeeper/ui.sh`, `hotkeys.sh`, `agent-table.sh`, `tui-refresh-loop.sh`, `tui-input-loop.sh`, `tui-signals.sh`, `tui-layout.sh` as in Ideas reference.
4. **Agents Templates**
   - `agents/templates/*` and sample build/test/lint agents.
5. **Config & State Dirs**
   - `config/liku.yaml`, `config/agents.yaml`, `config/paths.yaml` placeholders.
   - `state/` subdirectories (`sessions`, `agents`, `events`, `logs`).
6. **Install Scripts**
   - `install.sh`, `uninstall.sh` functioning for POSIX + WSL.
7. **README + Docs Hook**
   - Ensure `README.md` references new docs (architecture/event-bus/etc.).
8. **Basic Tests**
   - Shell test stubs in `tests/` per scaffold.

## 3. Acceptance Checks

- `./install.sh` completes in WSL (Doc update states this is required).
- Running `liku bookkeeper` launches the TUI skeleton without errors.
- `liku spawn <agent>` writes metadata under `state/agents/` and emits an event file.
- README includes quickstart referencing docs.

## 4. Delegation Package for Coding Agent

Provide the agent with:
- Link to `docs/architecture.md`, `docs/event-bus.md`, `docs/bookkeeper.md`, `docs/installation.md` for requirements.
- Summary of work items above + acceptance checks.
- Reminder to keep guidance JSON untouched (Phase 3), but create the necessary directories now.
- Command checklist: `chmod +x` for scripts, `shellcheck` optional, run provided tests (`tests/test-terminalID.sh`, etc.).

## 5. Next Steps After Merge

- Enable YOLO Supervisor workflow (already committed) to monitor the PR.
- Begin Phase 2 PRs for context store + event schemas, delegating via separate branches.

Use this plan when creating the GitHub PR and handing off to the coding agent.
