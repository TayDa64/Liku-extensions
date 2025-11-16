# LIKU Event Bus & Logging Spec

The event bus is the single source of truth for runtime telemetry, audit streaming, and remediation summaries.

## 1. Storage Layout

```
state/
  events/
    2025-11-16T120001Z.jsonl
    ...
agents/
  <agent-id>/
    commands/
      2025-11-16.jsonl
logs/
  guidance/
    guidance-<session>.json
```

- **Events**: JSON lines, one per emission, readable by CLI streaming tools.
- **Agent command chronicles**: JSON lines capturing ERROR/FAIL/Exception/Traceback events and the solution applied.
- **Guidance logs**: Session-scoped JSON arrays of Bookkeeper instructions; retention is user-managed.

## 2. JSONL Envelope

```json
{
  "ts": "2025-11-16T12:00:01.234Z",
  "type": "agent.spawn|agent.error|guidance.append|approval.request",
  "agent": "build",
  "terminal_id": "liku:2.1",
  "pid": 12345,
  "pgid": 12345,
  "term": "xterm-256color",
  "tty": "/dev/pts/3",
  "session": "liku-user-host-dev_pts_3",
  "payload": { ... },
  "meta": {
    "session": "session-abc",
    "user": "primary",
    "source": "liku-core|bookkeeper|plugin"
  }
}
```

Required fields: `ts`, `type`, `meta.session`. Fields such as `term`, `tty`, and `session` are populated automatically by `core/cli-environment.sh` whenever the runtime emits an event so operators know exactly which CLI/TUI spawned the action.

## 3. CLI Streaming

- `liku event stream --since 5m` – tail JSON lines using `tail -F` or `jq` for filtering.
- `liku event inspect <event-id>` – fetch a slice from JSONL by timestamp.
- `liku event export --type guidance.append` – dump only guidance additions.

All CLI utilities rely on POSIX shell or Node-based bundlers and run equally inside WSL.

## 4. Automatic Error Detection

Whenever output contains `ERROR`, `FAIL`, `Exception`, or `Traceback`, the runtime emits:

```json
{
  "ts": "...",
  "type": "agent.error",
  "agent": "build",
  "payload": {
    "command": "npm run build",
    "stderr": "Traceback ...",
    "resolution": "npm install"
  }
}
```

The same data is appended to `/agents/<id>/commands/DATE.jsonl` using the narrative sentence format. This ensures a human-auditable trail and enables Bookkeeper to summarize recent remediations.

## 5. Guidance Operations

- `guidance.append` events capture Bookkeeper prompts and actions.
- Listing guidance files triggers a synthetic `guidance.list` event so other agents know the operator is managing archives.
- When the user confirms deletion, Bookkeeper emits `guidance.delete.requested` (no file removal occurs automatically) and displays the command `rm logs/guidance/<file>.json`.

## 6. External Approval Hooks

To align with existing tools:

| Integration | Event Type |
| --- | --- |
| VS Code Workspace Trust | `approval.workspace_trust` |
| Claude Code Permissions | `approval.permission.toggle` |
| Gemini CLI Agent Mode | `approval.plan.review` |
| OpenAI Codex CLI | `approval.policy.set` |

These events record the operator’s preferences so they persist across CLI sessions and are enforced prior to HTTP exposure.

## 7. Retention & Auditing

- Event JSONL files rotate daily; old files can be archived manually.
- `/agents/<id>/commands` are kept for the life of the project unless removed by the operator.
- Guidance logs remain until the user deletes them (Bookkeeper only assists by listing and providing commands).

This spec keeps the data path transparent, CLI-friendly, and compliant with industry approval flows referenced throughout the Ideas folder.
