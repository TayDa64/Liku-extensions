# LIKU Bookkeeper Guide

Bookkeeper is the terminal-native command center for supervising subagents, issuing guidance, and keeping retention under user control.

## 1. Core Responsibilities

1. Monitor every tmux pane spawned by LIKU (TerminalID, PID, PGID, SID).
2. Display agent tables (status, last command, elapsed time) and hotkeys per the original scaffold.
3. Interpret events (build errors, test failures) and surface actionable prompts.
4. Maintain conversational UX so operators can request insights instead of memorizing commands.

## 2. Conversational Guidance Flow

**Listing archives**
- User: “Bookkeeper, list guidance files.”
- Bookkeeper scans `logs/guidance/*.json`, builds a table:
  |
  | ID | File | Session | Size | Updated |
  | --- | --- | --- | --- | --- |
  | 1 | `logs/guidance/guidance-2025-11-16.json` | session-abc | 12 KB | 2025-11-16 13:05 |
- Bookkeeper emits a `guidance.list` event and keeps the table visible until dismissed.

**Deleting archives**
- User: “Remove guidance #1.”
- Bookkeeper: “Confirm deletion of `logs/guidance/guidance-2025-11-16.json`? (yes/no)”
- On “yes,” Bookkeeper prints the manual instruction:
  ```bash
  rm logs/guidance/guidance-2025-11-16.json
  ```
  and emits `guidance.delete.requested`. Actual deletion is left to the operator.

This conversational approach mirrors the UX expectations set by VS Code, Claude Code, Gemini CLI, and Codex (approval prompts, explicit user consent).

## 3. Guidance Memory Behavior

- Active session guidance lives in `logs/guidance/<session>.json` (JSON array of prompts/responses).
- Files are never auto-rotated; Bookkeeper simply surfaces their metadata.
- `/agents/<id>/commands` summaries are cross-linked so operators can jump from a guidance entry to the remediation record.

## 4. Approval & Safety Modes

Bookkeeper visualizes approval modes drawn from the Ideas research:

| Mode | Inspired By | Behavior |
| --- | --- | --- |
| **Auto** | Codex `--full-auto` | Proceed without asking once the user sets defaults. |
| **Ask** | VS Code Workspace Trust dialog | Prompt the user before risky actions. |
| **Deny** | Claude Code sandbox default | Block actions unless explicitly allowed. |
| **Plan Review** | Gemini agent mode | Generate a plan and require approval per step. |

Operators switch modes from the TUI or via `bookkeeper set approval ask`. The chosen mode persists in SQLite and is enforced before Bookkeeper triggers subagent operations.

## 5. Hotkeys & Commands

- `R` – Refresh tables
- `K` – Request agent termination (sends event, guardian enforces PGID kill)
- `G` – Start guidance conversation
- `L` – Focus guidance archive listing view (shows the latest table described above)

These hotkeys complement the conversational prompts for power users who prefer keyboard flows.

## 6. UX Principles

1. **CLI-first** – All features usable inside terminals, including WSL.
2. **Human-friendly sentences** – Mirror the `/agents/<id>/commands` style when summarizing actions.
3. **Explain before acting** – Always present what will happen (e.g., exact file path, PGID) before suggesting a command.
4. **No hidden deletion** – Bookkeeper never deletes user data.

With these guardrails, Bookkeeper becomes the centralized, user-friendly interface envisioned across the Ideas documents.
