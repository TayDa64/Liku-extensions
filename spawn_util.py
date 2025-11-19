
import sys
import subprocess
from database import log_event

def spawn_agent(name: str, goal: str) -> bool:
    """
    Spawns an agent as a direct subprocess and waits for it to complete.
    The agent_runner script is responsible for logging the detailed output.
    """
    cmd = [sys.executable, "agent_runner.py", name, goal]
    
    try:
        # Use subprocess.run to execute the agent and wait for it to complete.
        # This allows us to confirm the agent ran, while the detailed logging
        # happens within the agent_runner itself.
        subprocess.run(cmd, check=True)
        log_event(name, "Spawn signal sent and processed.", "SPAWN")
        return True

    except Exception as e:
        error_message = f"Failed to spawn agent {name}: {e}"
        log_event(name, error_message, "ERROR")
        return False
