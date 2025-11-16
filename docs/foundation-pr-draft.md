# Phase 1 PR Draft – Runtime & Bookkeeper Scaffold

**Branch:** `feature/foundation-runtime`
**Title:** `Phase 1 – Runtime & Bookkeeper Scaffold`
**Labels:** `phase:foundation`, `yolo`, `needs-review`
**Reviewers:** Core maintainers + coding agent

## Summary
- Restore the LIKU runtime scaffold (core scripts, bin wrappers, Bookkeeper TUI, install scripts) exactly as outlined in `docs/foundation-plan.md`.
- Ensure `install.sh` works on POSIX/WSL and `liku bookkeeper` launches the TUI skeleton.
- Wire the event bus so `liku spawn <agent>` writes metadata and emits an event file.
- Reference the new documentation (`docs/architecture.md`, `docs/event-bus.md`, etc.) from the README.

## Checklist
- [ ] Add `core/*.sh`, `bin/*`, `bookkeeper/*`, `agents/*`, `config/*`, `state/*`, `tests/*` from scaffold.
- [ ] Mark scripts executable (`chmod +x`).
- [ ] Update `README.md` quickstart.
- [ ] Run validation commands listed in `docs/foundation-pr-checklist.md`.
- [ ] Confirm YOLO Supervisor workflow picks up the `yolo` label.

## Testing
```bash
chmod +x bin/* core/*.sh bookkeeper/*.sh install.sh uninstall.sh
./install.sh
liku status
liku bookkeeper
liku spawn build-agent
ls state/agents
```

## Notes
- Guidance JSON features arrive in later phases; just create placeholder directories/files (e.g., `logs/guidance/.gitkeep`).
- Maintain POSIX compliance for shell scripts so everything runs inside WSL.
- Mention in the PR body that YOLO Supervisor is enabled to assist with failure handling.
