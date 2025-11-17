#!/usr/bin/env python3
import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root to sys.path for module discovery
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.liku_client import LikuClient

class JokeAgent:
    def __init__(self, session_key: str):
        self.session_key = session_key
        self.state_file = Path.home() / ".liku" / "state" / "agents" / f"{session_key}.json"
        self.state = self._load_state()
        self.client = LikuClient()

    def _load_state(self) -> Dict[str, Any]:
        """Loads the agent's state from a file."""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {"state": "TELLING"}

    def _save_state(self):
        """Saves the agent's state to a file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state))

    def get_joke(self) -> Optional[str]:
        """Fetches a random joke from the Official Joke API."""
        try:
            response = requests.get("https://official-joke-api.appspot.com/jokes/random")
            response.raise_for_status()
            joke_data = response.json()
            return f"{joke_data['setup']} - {joke_data['punchline']}"
        except requests.RequestException as e:
            self.emit_message(f"Sorry, I couldn't fetch a joke right now. Error: {e}")
            return None

    def emit_message(self, message: str):
        """Emits a message from the agent."""
        self.client.emit_event("agent.message", message, session_key=self.session_key)

    def handle_event(self, event: Dict[str, Any]):
        """Handles an incoming event."""
        if self.state.get("state") == "TELLING":
            joke = self.get_joke()
            if joke:
                self.emit_message(joke)
                self.emit_message("Your turn! Tell me a joke.")
                self.state["state"] = "LISTENING"
                self._save_state()
        elif self.state.get("state") == "LISTENING":
            # In a real implementation, we would parse the event to get the user's message
            # and check if it's a joke. For now, we'll just assume any message is a joke.
            self.emit_message("Haha, that's a good one! Here's another:")
            joke = self.get_joke()
            if joke:
                self.emit_message(joke)
                self.emit_message("Your turn! Tell me a joke.")
                self.state["state"] = "LISTENING"
                self._save_state()

def main():
    # The session key should be passed as a command-line argument
    if len(sys.argv) < 2:
        print("Usage: joke_agent.py <session_key>")
        sys.exit(1)
    
    session_key = sys.argv[1]
    agent = JokeAgent(session_key)

    # Initial state
    if agent.state.get("state") == "TELLING":
        joke = agent.get_joke()
        if joke:
            agent.emit_message(joke)
            agent.emit_message("Your turn! Tell me a joke.")
            agent.state["state"] = "LISTENING"
            agent._save_state()

    # Main loop to process events
    for line in sys.stdin:
        try:
            event = json.loads(line)
            agent.handle_event(event)
        except json.JSONDecodeError:
            # Ignore non-JSON lines
            pass

if __name__ == "__main__":
    main()
