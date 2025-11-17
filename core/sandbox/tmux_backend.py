#!/usr/bin/env python3
"""
tmux-based sandbox for executing agent commands in separate panes.
"""

from typing import Any, Dict, Optional

from liku.sandbox.base import Sandbox, SandboxResource
from liku.event_bus import EventBus
from liku.tmux_manager import TmuxManager


class TmuxSandbox(Sandbox):
    """
    A sandbox implementation that uses tmux panes to provide execution
    environments for agents.
    """

    def __init__(self, event_bus: EventBus, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the tmux sandbox.
        
        Args:
            event_bus: The system event bus.
            config: Global tmux configuration.
        """
        self.tmux_manager = TmuxManager(event_bus=event_bus)

    def create(
        self,
        agent_name: str,
        session_key: str, # session_key is the tmux session name
        command: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SandboxResource:
        """Create a new tmux pane for the agent."""
        pane = self.tmux_manager.create_pane(
            session=session_key,
            command=command,
            agent_name=agent_name
        )
        return SandboxResource(id=pane.pane_id, pid=pane.pane_pid)

    def execute(self, resource_id: str, command: str, literal: bool = False) -> None:
        """Send keys to the specified tmux pane."""
        self.tmux_manager.send_keys(pane_id=resource_id, keys=command, literal=literal)

    def capture_output(self, resource_id: str, lines: int = 50) -> str:
        """Capture the output from the specified tmux pane."""
        return self.tmux_manager.capture_pane(pane_id=resource_id, start=-lines)

    def kill(self, resource_id: str, agent_name: Optional[str] = None) -> None:
        """Kill the specified tmux pane."""
        self.tmux_manager.kill_pane(pane_id=resource_id, agent_name=agent_name)
