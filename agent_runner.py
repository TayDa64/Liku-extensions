
import sys
import subprocess
import os
from database import log_event, init_db

def run_agent(agent_name: str, goal: str) -> None:
    """
    Runs the specified agent's handler script, captures its output, and logs it.
    """
    print(f"--- AGENT: {agent_name} ---")
    print(f"Goal: {goal}")
    init_db()
    log_event(agent_name, f"Awakened. Goal: {goal}", "STARTUP")

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        handler_path = os.path.join(script_dir, 'agents', agent_name, 'handler.sh')

        if not os.path.exists(handler_path):
            log_event(agent_name, f"Fatal: handler.sh not found at {handler_path}", "ERROR")
            print(f"[{agent_name}] Error: handler.sh not found.")
            return

        result = subprocess.run(
            ['bash', handler_path, goal],
            capture_output=True,
            text=True,
            check=False,
            cwd=script_dir
        )

        if result.stdout:
            log_event(agent_name, result.stdout.strip(), "STDOUT")
            print("--- Agent STDOUT ---")
            print(result.stdout.strip())

        if result.stderr:
            log_event(agent_name, result.stderr.strip(), "STDERR")
            print("--- Agent STDERR ---")
            print(result.stderr.strip())

        if result.returncode == 0:
            log_event(agent_name, "Agent task completed successfully.", "RESULT")
        else:
            log_event(agent_name, f"Agent task failed with exit code {result.returncode}.", "ERROR")

    except Exception as e:
        error_message = f"An unexpected error occurred in agent_runner: {e}"
        log_event(agent_name, error_message, "ERROR")
        print(f"[{agent_name}] Fatal runner error: {e}")
    finally:
        log_event(agent_name, "Agent shutting down.", "SHUTDOWN")
        print(f"[{agent_name}] Shutdown.")


def main():
    if len(sys.argv) < 3:
        print("Usage: python agent_runner.py <agent_name> <goal>")
        sys.exit(1)
    
    agent_name = sys.argv[1]
    goal = " ".join(sys.argv[2:])
    run_agent(agent_name, goal)


if __name__ == "__main__":
    main()
