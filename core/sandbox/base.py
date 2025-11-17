#!/usr/bin/env python3
"""
Abstract base class for execution sandboxes.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, NamedTuple


class SandboxResource(NamedTuple):
    """Represents a resource created by a sandbox, like a pane or container."""
    id: str
    pid: Optional[int] = None
    details: Dict[str, Any] = {}


class Sandbox(ABC):
    """
    An abstract base class for an execution environment that can run commands,
    be managed, and have resources constrained.
    """

    @abstractmethod
    def create(
        self,
        agent_name: str,
        session_key: str,
        command: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SandboxResource:
        """
        Create a new sandboxed environment (e.g., a tmux pane or a Docker container).
        
        Args:
            agent_name: The name of the agent this sandbox is for.
            session_key: The unique session key for this agent instance.
            command: The initial command to run.
            config: Agent-specific configuration.
            
        Returns:
            A SandboxResource tuple containing the ID and other details of the created resource.
        """
        pass

    @abstractmethod
    def execute(self, resource_id: str, command: str, literal: bool = False) -> None:
        """
        Execute a command within a given sandbox resource.
        
        Args:
            resource_id: The ID of the sandbox resource (e.g., pane_id or container_id).
            command: The command or keys to send.
            literal: Whether to treat the command as a literal string (for tmux).
        """
        pass

    @abstractmethod
    def capture_output(self, resource_id: str, lines: int = 50) -> str:
        """
        Capture the recent output from a sandbox resource.
        
        Args:
            resource_id: The ID of the sandbox resource.
            lines: The number of recent lines to capture.
            
        Returns:
            The captured output as a string.
        """
        pass

    @abstractmethod
    def kill(self, resource_id: str, agent_name: Optional[str] = None) -> None:
        """
        Kill/destroy a sandbox resource.
        
        Args:
            resource_id: The ID of the sandbox resource to kill.
            agent_name: The name of the agent associated with the resource.
        """
        pass
