# LIKU Bookkeeper Guide

Bookkeeper is the terminal-native command center for supervising subagents, issuing guidance, and keeping retention under user control.

## 1. Core Responsibilities

1. Monitor every tmux pane spawned by LIKU (TerminalID, PID, PGID, SID).
2. Display enriched agent tables (status, mode, terminal, current command) with arrow-key selection and a detail panel.
3. Surface tmux-agent activity (`liku exec`) alongside the agent table so users can confirm Option A sessions are running even when the IDE shows a single terminal buffer.
4. Emit and interpret structured events (guidance, autocorrect, pause/resume) so operators can steer subagents safely.
5. Maintain conversational UX so operators can request insights instead of memorizing commands.

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

Alongside the conversational prompts, the Bookkeeper TUI now includes a selectable agent table and a contextual detail pane. Use the arrow keys to highlight an agent, then trigger hotkeys such as `D` (describe) or `L` (tail logs) to populate the detail pane with structured insight or captured tmux output. This keeps the back-and-forth grounded in the exact pane/TTY metadata recorded inside `~/.liku/state/agents/*.json`.

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

Operators switch modes from the TUI or via `bookkeeper set approval ask`. The chosen mode is persisted alongside each agent record in `~/.liku/state/agents/<agent>.json` and is enforced before Bookkeeper triggers subagent operations.

## 5. Hotkeys & Commands

| Key / Control | Purpose |
| --- | --- |
| `↑` / `↓` | Move the selection cursor through the live agent table. |
| `R` | Re-render the table and detail pane without changing selection. |
| `D` | Describe the selected agent (PID, session, pane, current command, mode). |
| `L` | Capture and display the last ~50 lines from the agent’s tmux pane. |
| `G` | Prompt for natural-language guidance and emit an `agent.elicit` event with the typed instructions. |
| `A` | Prompt for an auto-correction suggestion and emit `agent.autocorrect`. |
| `P` / `C` | Send SIGSTOP / SIGCONT to pause or resume the agent’s PID. |
| `S` | Cycle through the predefined approval/safety modes for the highlighted agent. |
| `W` | Jump to the agent’s tmux pane (or print the manual `tmux select-pane` command when running outside tmux). |
| `K` | Request agent termination via `agent.kill` (guardian scripts handle the enforcement). |
| `Q` | Quit the Bookkeeper UI. |

These hotkeys complement the conversational prompts for power users who prefer keyboard flows.

### Tmux Activity Panel

Directly beneath the agent list, Bookkeeper renders the latest entries from `~/.liku/state/panes/pane-*.json`, which are produced every time `liku exec -- <command>` runs. The table shows:

- `Terminal ID` – the tmux `session:window.pane` identifier (Option A TerminalID).
- `Status` – IDLE/RUNNING/WATCHING derived from `tmux display-message`.
- `Label` – either the exec `--label` or the tmux window name.
- `Last Command` – truncated shell command captured at launch time.
- `Updated` – the ISO8601 timestamp stored in the pane JSON.

This ensures contributors can see that LIKU spun up new panes/sessions even if their IDE only shows a single PowerShell/WSL buffer, satisfying the UI best practices called out in the Ideas documents.

## 6. UX Principles

1. **CLI-first** – All features usable inside terminals, including WSL.
2. **Human-friendly sentences** – Mirror the `/agents/<id>/commands` style when summarizing actions.
3. **Explain before acting** – Always present what will happen (e.g., exact file path, PGID) before suggesting a command.
4. **No hidden deletion** – Bookkeeper never deletes user data.
5. **Terminal awareness** – `core/cli-environment.sh` validates that the active terminal supports curses and surfaces the detected `TERM`, `TTY`, and tmux session inside the TUI banner so operators can confirm they are steering the intended interface.

With these guardrails, Bookkeeper becomes the centralized, user-friendly interface envisioned across the Ideas documents.
