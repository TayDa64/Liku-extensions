# LIKU Architecture Blueprint

This document translates the brainstormed LIKU scaffold (see `Ideas/extension-brainstorming*.md`) into an actionable architecture for the production-grade extension.

## 1. Runtime Pillars

1. **Terminal Orchestrator** – `core/runtime.sh` coordinates tmux sessions, TerminalIDs, PID/PGID/SID tracking, and subagent lifecycle hooks.
   - `core/cli-environment.sh` captures the active shell/TTY/tmux context so runtime actions stay anchored to the operator’s CLI.
2. **Context Store** – SQLite for structured metadata (agents, approvals, session summaries) plus append-only JSONL traces for high-volume events.
3. **Event Bus** – JSONL files under `state/events/` with CLI-first streaming, mirroring VS Code Workspace Trust and Claude/Gemini/Codex approval signals.
4. **Bookkeeper TUI** – Monitors agents, captures guidance, and converses with the operator ("list guidance files", "remove guidance #2").
5. **CLI Utilities** – All automation runs via POSIX shell + Node-based bundlers; Windows users engage through WSL, never native PowerShell installers.

## 2. Data & Persistence

| Path | Purpose |
| --- | --- |
| `state/sessions/<session-id>/context.db` | SQLite database storing agent metadata, approval defaults, and per-user guidance settings. |
| `state/events/*.jsonl` | Append-only event stream (see `docs/event-bus.md`). |
| `state/agents/<agent>.json` | Subagent runtime metadata (TerminalID, PID, PGID, SID). |
| `logs/guidance/<session>.json` | Per-session Bookkeeper memory; never converted to markdown. |
| `agents/<id>/commands` | Directory where remediation chronicle files live (`YYYYMMDD.jsonl`). |

Guidance JSON files persist until the user manually deletes them. Bookkeeper exposes the current inventory and confirms before advising manual removal.

## 3. Event Flow Overview

1. Agent lifecycle actions emit events via `core/event-bus.sh`.
2. Bookkeeper subscribes over CLI streaming (see `liku-eventd`).
3. ERROR/FAIL/Exception/Traceback patterns immediately create entries inside `/agents/<id>/commands` with the sentence template:
   ```
   <ISO8601> agent <name> executed <command> … resolved with <solution>
   ```
4. Guidance prompts append contextual instructions to the active `logs/guidance/<session>.json` file.
5. HTTP exposures (future phases) are gated until per-user approvals and guidance defaults are stored.

## 4. Phase Roadmap

| Phase | Goal |
| --- | --- |
| **P1 – Runtime Foundations** | Implement tmux TerminalID tracking, PID tools, event emission, and Bookkeeper TUI skeleton (per scaffold). |
| **P2 – Context & Events** | Introduce SQLite context-store, JSONL event schemas, and `/agents/<id>/commands` logging. |
| **P3 – Guidance Memory** | Persist per-session `logs/guidance` files, add conversational listing/deletion prompts, and enforce manual retention. |
| **P4 – Approvals & Safety** | Mirror VS Code Workspace Trust, Claude Code permissions, Gemini CLI plan approvals, and Codex `/approvals` before enabling HTTP endpoints. |
| **P5 – Telemetry & Rubric Compliance** | Apply the weighted rubric (see `docs/rubric.md`) to ensure production readiness before expansion. |

## 5. Conversational Guidance UX

- **List**: User asks "Bookkeeper, list guidance files". Bookkeeper returns a table (ID, filename, session, size, last updated) derived from `logs/guidance/*.json`.
- **Delete**: User says "Remove guidance #2". Bookkeeper confirms and responds with the exact file path plus POSIX command suggestion (e.g., `rm logs/guidance/guidance-2025-11-16.json`). Actual deletion is manual, satisfying retention requirements.

## 6. Compliance Hooks

- POSIX shell install scripts (`install.sh`) remain the source of truth; Node bundlers package any agent tooling.
- Windows instructions always reference WSL (`wsl.exe --distribution Ubuntu ...`).
- Bookkeeper cannot expose HTTP endpoints until `config/liku.yaml` contains explicit approvals + guidance defaults.
- CLI-first auditing: before any HTTP server spins up, run `liku event stream` (exact commands in `docs/event-bus.md`).

This architecture anchors all derivative docs (event bus, protocol, installation, and rubric) to ensure consistency with the original brainstorm and current best practices.
