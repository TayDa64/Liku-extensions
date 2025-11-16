# LIKU Testing Guide

This guide describes how to verify the LIKU runtime across the environments most contributors use today: VS Code Insiders, GitHub Copilot CLI, Gemini CLI, and ChatGPT Codex CLI. Each workflow assumes you already have the repository cloned and the baseline prerequisites installed (POSIX shell, `tmux`, `sqlite3`, `inotifywait`, Node.js 20+, Python 3.11+, Git).

## 0. Global Preparation

Before running any scenario:

1. Ensure executable bits are set:
   ```bash
   chmod +x install.sh uninstall.sh bin/* core/*.sh bookkeeper/*.sh agents/*/*.sh
   ```
2. Install LIKU into your home directory:
   ```bash
   ./install.sh
   ```
3. Open a **new** terminal and run the doctor to catch dependency issues:
   ```bash
   likuctl doctor
   ```
4. Verify PATH updates by running:
   ```bash
   liku status
   ```
5. Confirm `tmux` works (`tmux -V`).
6. On Windows, launch the Ubuntu/WSL terminal and run all commands there.

With the basics complete, follow one (or all) of the environment-specific flows below.

---

## 1. VS Code Insiders Workflow

1. **Launch VS Code Insiders** and open the `Liku-extensions` folder (`File → Open Folder…`).
2. **Select the WSL/Remote environment** (if on Windows) using the Remote Explorer so all shells run inside Ubuntu.
3. **Install recommended extensions** (ShellCheck, Bash IDE) when prompted.
4. **Open a new integrated terminal** (`Terminal → New Terminal`). Confirm it uses bash/zsh and WSL (if applicable).
5. **Restore dependencies**:
   ```bash
   sudo apt update
   sudo apt install -y tmux inotify-tools sqlite3
   npm install --global @githubnext/cli # optional helper
   ```
6. **Run the installer again from the integrated terminal** (ensures VS Code shell picks up the latest build):
   ```bash
   ./install.sh
   ```
7. **Spawn sample agents** to verify tmux + Bookkeeper wiring:
   ```bash
   liku spawn build-agent
   liku spawn test-agent
   ```
   - Observe new tmux panes appear (if you started from an existing tmux session) or check `tmux ls` to see the `liku-<tty>` session created for you.
8. **Start Bookkeeper** in another terminal tab:
   ```bash
   liku bookkeeper
   ```
   - Confirm the banner shows `TERM`, `TTY`, and `Session` values that match your VS Code terminal pane.
9. **Tail events** to ensure audit logs are created:
   ```bash
   liku event stream --since 1m | jq '.'
   ```
10. **Review artifacts** inside the Explorer:
    - `~/.liku/state/agents/*.json` should list each agent with the detected terminal metadata.
    - `state/events/*.event` files should reflect every spawn/bookkeeper action.

This completes the Insiders-centric test run.

---

## 2. GitHub Copilot CLI Workflow

> Requires the `github-copilot-cli` preview (`npm install -g @githubnext/github-copilot-cli`) and a GitHub account with Copilot access.

1. **Authenticate** Copilot CLI:
   ```bash
   github-copilot-cli auth login
   ```
2. **Ask Copilot CLI to draft a test plan** inside the repo root:
   ```bash
   github-copilot-cli task "verify liku install"
   ```
   - Accept the generated plan or tweak it interactively.
3. **Execute Copilot CLI suggestions** (typically it proposes commands similar to):
   ```bash
   ./install.sh
   liku status
   liku spawn lint-agent
   ```
4. **Validate tmux panes** with Copilot’s recommended follow-up command:
   ```bash
   tmux list-panes -a -F '#S #T #{pane_pid} #{pane_title}'
   ```
5. **Confirm Bookkeeper rendering** by letting Copilot CLI launch it:
   ```bash
   github-copilot-cli shell "liku bookkeeper"
   ```
   - Copilot CLI keeps the context so you can narrate what you see and ask for troubleshooting steps if the TUI fails.
6. **Inspect logs** the CLI references:
   ```bash
   cat ~/.liku/state/session/env.json
   cat ~/.liku/state/agents/build-agent.json
   ```
7. **Close Copilot CLI session** once all checks pass: `exit`.

This demonstrates that LIKU behaves consistently when command sequences come from Copilot CLI prompts.

---

## 3. Gemini CLI Workflow

> Assumes you installed the Gemini Agent Mode CLI (`pip install google-genai-cli`, placeholder name `gemini`).

1. **Authenticate** with your Google API key:
   ```bash
   export GEMINI_API_KEY=... # or use the CLI's login command
   gemini auth login
   ```
2. **Start a Gemini Agent session** in the repo root:
   ```bash
   gemini agent start --name liku-audit
   ```
3. **Request a setup script** from Gemini:
   ```bash
   gemini> Run the LIKU installer and confirm Bookkeeper works
   ```
   - Gemini will suggest commands you can approve/deny (mirroring LIKU’s own approval philosophy).
4. **Approve the proposed shell steps** (expect variants of):
   ```bash
   ./install.sh
   liku spawn build-agent
   liku event stream --since 2m
   ```
5. **Inspect the generated transcript** (Gemini saves it under `~/.config/gemini/sessions/`). Keep it for auditing beside LIKU’s JSONL logs.
6. **Exit agent mode** when done:
   ```bash
   gemini agent stop liku-audit
   ```
7. **Cross-check LIKU logs** to ensure the Gemini-driven session is recorded:
   ```bash
   jq '.' ~/.liku/state/agents/build-agent.json
   tail ~/.liku/state/events/*.event
   ```

> **Gemini CLI extension crash**: If you see an error similar to `Error loading commands from ... .gemini\extensions\nanobanana\commands: DOMException [AbortError]`, delete the offending extension directory and reinstall the CLI:
> ```powershell
> Remove-Item -Recurse -Force "$env:USERPROFILE\.gemini\extensions\nanobanana"
> npm install -g @google/gemini-cli@latest
> ```
> Then rerun `gemini agent start --name liku-audit`. The CLI falls back to its core commands once third-party extensions are removed.

This validates LIKU from inside the Gemini CLI’s agent workflow and mirrors the plan/approval UX highlighted in the protocol document.

---

## 4. ChatGPT Codex CLI Workflow

> For OpenAI Codex CLI users (`pip install openai-codex-cli` or `npm install -g @openai/codex-cli`). Adjust commands to the specific distribution you use.

1. **Log in** with your OpenAI API key:
   ```bash
   export OPENAI_API_KEY=...
   codex login
   ```
2. **Initialize a Codex session** in "plan-first" mode to mirror LIKU’s approvals:
   ```bash
   codex plan "Test LIKU runtime"
   ```
3. **Let Codex suggest a command batch** (should include `./install.sh`, `liku status`, `liku spawn ...`). Review and approve step-by-step.
4. **Execute the Codex-generated script** automatically:
   ```bash
   codex run plan
   ```
5. **Have Codex inspect outputs** by running follow-up queries like:
   ```bash
   codex ask "What is inside ~/.liku/state/session/env.json?"
   ```
   - Provide the file contents when prompted; Codex will reason about correctness.
6. **Request Bookkeeper validation**:
   ```bash
   codex run "liku bookkeeper"
   ```
   - Confirm the CLI echoes the TUI banner to prove Codex is sharing your terminal context.
7. **Save the Codex transcript** (`codex history export`) alongside the LIKU event logs for audit parity.

This path ensures LIKU behaves when driven by Codex’s approval-centric CLI, reinforcing the same safety posture described in `docs/protocol.md`.

---

## 5. What to Look For

Across all environments, testing is successful when:

- `liku status` lists the scaffold agents without errors.
- Spawning an agent creates a tmux pane/session named after your detected TTY (see `~/.liku/state/session/env.json`).
- Bookkeeper refuses to run in unsupported terminals and otherwise displays the environment banner.
- `state/events/*.event` files include `term`, `tty`, and `session` metadata for each action.
- `/agents/<name>/commands/DATE.jsonl` gains entries whenever you force an `ERROR`/`FAIL` condition in an agent window.

If any environment behaves differently, capture the CLI transcript, the relevant JSON state files, and file an issue referencing this guide.
