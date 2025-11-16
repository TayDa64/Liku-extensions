# LIKU Protocol & Approval Framework

This protocol synthesizes the Tier-2/Tier-3 tmux guidance (see `Ideas/extension-brainstorming-tty` and `Ideas/extension-brainstorming-RFC-007-AISTOP`) with modern approval practices from VS Code, Claude Code, Gemini CLI, and OpenAI Codex.

## 1. Core Principles

1. **Zero Interference** – Never execute commands in user terminals; use LIKU-managed tmux sessions.
2. **State Awareness** – Inspect TerminalID, PID, PGID, SID, and job tables before issuing commands.
3. **Process Group Responsibility** – Send signals to PGID/SID to affect entire jobs safely.
4. **CLI-First Auditing** – All actions observable via CLI streaming before HTTP endpoints exist.
5. **User Consent** – Approval modes must be explicit and stored per user.

## 2. Lifecycle States

```
DISCOVER → INSPECT → PREPARE WINDOW → EXECUTE → COMPLETE → ARCHIVE
```

Each transition emits an event (see `docs/event-bus.md`). Failures revert to `DISCOVER` with diagnostic info.

## 3. Approval Modes

| Mode | Description | Source Inspiration |
| --- | --- | --- |
| `auto` | Executes allowed operations silently once configured. | Codex `--full-auto` |
| `ask` | Prompts user for confirmation on each potentially destructive action. | VS Code Workspace Trust |
| `deny` | Blocks the action until operator toggles mode. | Claude Code sandbox defaults |
| `plan-review` | Produces a plan, awaits approval per stage, then executes. | Gemini CLI Agent Mode |

Approval state is stored in SQLite (`context_store.approvals`). CLI commands:

```
bookkeeper set approval ask
bookkeeper show approval
```

Bookkeeper also surfaces the current mode in its status bar.

## 4. Guidance Protocol

1. Subagents emit `guidance.request` when they need feedback.
2. Bookkeeper prompts the user, logs the response to `logs/guidance/<session>.json`, and emits `guidance.append`.
3. If the user references historical guidance, Bookkeeper reads the JSON file and summarizes entries without converting formats.

## 5. Error Remediation Protocol

1. Detect error keywords -> emit `agent.error` event.
2. Append remediation sentence to `/agents/<id>/commands/DATE.jsonl`.
3. Notify Bookkeeper so it can display the remediation summary immediately.

## 6. Conversational File Management

- Listing and deletion requests occur via natural language (see `docs/bookkeeper.md`).
- Bookkeeper never deletes files; it only confirms and shows the manual POSIX command.
- Events `guidance.list` and `guidance.delete.requested` capture audit context.

## 7. Retention Policy

- Guidance JSON files persist until the user removes them.
- `/agents/<id>/commands` persist for the project lifecycle.
- Event logs rotate by day but should be archived before deletion to maintain traceability.

## 8. Compliance Checklist

- [ ] Commands only run in `liku` tmux sessions.
- [ ] Approval mode stored before executing agent tasks.
- [ ] `/agents/<id>/commands` updated for every remediation.
- [ ] Guidance logs listed/deleted via conversational prompts.
- [ ] HTTP endpoints disabled until approvals + guidance defaults configured.

This protocol ensures LIKU remains safe, auditable, and aligned with industry standards as the extension matures.
