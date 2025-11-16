# Phase 1 Foundation – Coding Agent Checklist

Use this document when creating the `feature/foundation-runtime` branch and opening the corresponding PR.

## Branch & PR Metadata
- Branch: `feature/foundation-runtime`
- PR Title: `Phase 1 – Runtime & Bookkeeper Scaffold`
- Labels: `phase:foundation`, `yolo`, `needs-review`
- Link YOLO Supervisor workflow by adding label `yolo` so GH Actions monitors it.

## Required Files (restore from Ideas scaffold)
1. `core/` scripts:
   - `runtime.sh`, `pid-tools.sh`, `terminalID.sh`, `context-store.sh` (stub), `event-bus.sh`, `subagent-engine.sh`, `safety-guards.sh`, `orchestrator.sh`, `state-machine.sh`
2. `bin/` executables:
   - `liku`, `liku-agent`, `liku-bookkeeper`, `liku-tmux`, `liku-daemon`, `liku-eventd`
3. `bookkeeper/` TUI skeleton:
   - `ui.sh`, `hotkeys.sh`, `agent-table.sh`, `tui-refresh-loop.sh`, `tui-input-loop.sh`, `tui-signals.sh`, `tui-layout.sh`
4. `agents/` templates + sample agents (build/test/lint)
5. `config/` placeholders (`liku.yaml`, `agents.yaml`, `paths.yaml`)
6. `state/` directories (`sessions`, `agents`, `events`, `logs`)
7. `install.sh` / `uninstall.sh`
8. `README.md` updates referencing `docs/`
9. `tests/` shell stubs per scaffold

## Acceptance Criteria
- `./install.sh` completes on POSIX/WSL.
- `liku bookkeeper` launches the TUI without runtime errors.
- `liku spawn <agent>` records metadata under `state/agents/` and emits an event file.
- Executables marked executable (`chmod +x`).
- Tests in `tests/` runnable (placeholders may simply echo TODO but should exist).

## Validation Commands
```bash
chmod +x bin/* core/*.sh bookkeeper/*.sh install.sh uninstall.sh
./install.sh
liku status
liku bookkeeper
liku spawn build-agent
ls state/agents
```

## Notes
- Guidance JSON is not implemented yet; just create `logs/guidance/.gitkeep` for later phases.
- Keep code POSIX-compliant so it works under WSL.
- After PR creation, mention YOLO Supervisor workflow in the description.
