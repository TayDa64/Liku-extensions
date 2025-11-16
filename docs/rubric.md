# LIKU Production-Readiness Rubric

Use this weighted rubric to self-evaluate the extension before shipping new phases.

## Scoring Overview

| Category | Weight | Pass Criteria |
| --- | --- | --- |
| **Context Integrity** | 40% | Accurate SQLite + JSONL persistence, `/agents/<id>/commands` logging, guidance files discoverable and untouched until user removal. |
| **Event & Audit Fidelity** | 30% | Event schemas match `docs/event-bus.md`, CLI streaming works, ERROR detector populates remediation logs, approvals recorded before execution. |
| **Guidance UX & Approvals** | 20% | Bookkeeper conversational prompts (“list guidance files”, “remove #n”) function, approval modes align with VS Code/Claude/Gemini/Codex patterns, confirmations are explicit. |
| **Installer & CLI Compliance** | 10% | POSIX + Node installers succeed, WSL instructions validated, HTTP endpoints remain disabled until approvals/guidance defaults configured. |

Total score = sum(weight * (0 or 1)). Target ≥ 0.9 before labeling a release “production ready.”

## Evaluation Checklist

### Context Integrity (0.4)
- [ ] `logs/guidance/<session>.json` updates per session.
- [ ] No markdown conversion or auto-deletion.
- [ ] `/agents/<id>/commands` contains remediation sentences for every error.

### Event & Audit Fidelity (0.3)
- [ ] JSONL events include all required fields (`ts`, `type`, `meta.session`).
- [ ] `liku event stream` shows real-time updates without HTTP services.
- [ ] Error detector captures all `ERROR|FAIL|Exception|Traceback` cases.

### Guidance UX & Approvals (0.2)
- [ ] Bookkeeper table listing is readable (ID, file, session, size, updated).
- [ ] Deletion flow confirms and shows manual `rm` command.
- [ ] Approval mode persisted and displayed in UI.

### Installer & CLI Compliance (0.1)
- [ ] `install.sh`/`uninstall.sh` complete on POSIX + WSL.
- [ ] Documentation references WSL for Windows users (no PowerShell scripts).
- [ ] HTTP endpoints disabled until approvals configured.

## Usage

1. Evaluate each checkbox before major releases.
2. Multiply the number of satisfied items in a category by its weight fraction to approximate readiness.
3. If score < 0.9, address failing categories before proceeding to the next phase.

This rubric enforces the best practices derived from the Ideas research and ensures LIKU remains audit-ready.
