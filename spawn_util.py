import sys
from database import log_event
from core.window_manager import get_window_manager

def spawn_agent(name: str, goal: str) -> bool:
    """
    Spawns an agent in a new window/pane using the WindowManager.
    """
    try:
        manager = get_window_manager()
        log_event(name, "Window manager initialized.", "SPAWN")

        # Ensure the session/environment is ready
        manager.ensure_session("liku-agents")
        
        command = [sys.executable, "tay_cli.py", "--name", name, "--goal", goal]
        
        pane = manager.create_pane(
            session="liku-agents",
            command=command,
            agent_name=name
        )
        
        if pane:
            log_event(name, f"Agent spawned in new pane: {pane.pane_id}", "SPAWN")
            return True
        else:
            log_event(name, "Failed to create pane for agent.", "ERROR")
            return False

    except Exception as e:
        error_message = f"Failed to spawn agent {name}: {e}"
        log_event(name, error_message, "ERROR")
        print(error_message, file=sys.stderr) # Add this line for debugging
        return False
