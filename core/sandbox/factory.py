#!/usr/bin/env python3
"""
Factory for creating sandbox instances based on agent configuration.
"""

from typing import Any, Dict, Optional

from liku.sandbox.base import Sandbox
from liku.sandbox.docker_backend import DockerSandbox
from liku.sandbox.tmux_backend import TmuxSandbox
from liku.event_bus import EventBus


class SandboxFactory:
    """
    Creates and configures sandbox instances.
    """
    
    _instances: Dict[str, Sandbox] = {}

    @staticmethod
    def get_sandbox(
        agent_config: Dict[str, Any],
        global_config: Dict[str, Any],
        event_bus: EventBus
    ) -> Sandbox:
        """
        Get a sandbox instance based on the agent's configuration.
        
        This factory will return a cached instance of a sandbox backend if one
        has already been initialized, to avoid re-creating expensive clients
        (like the Docker client).
        
        Args:
            agent_config: The specific configuration for the agent.
            global_config: The global system configuration.
            event_bus: The system event bus, passed to sandbox backends.
            
        Returns:
            An initialized Sandbox instance.
        """
        # Determine the sandbox mode. Default to 'tmux'.
        policies = agent_config.get("policies", {})
        mode = policies.get("sandbox_mode", "tmux")

        # Check cache first
        if mode in SandboxFactory._instances:
            return SandboxFactory._instances[mode]

        # Create new instance if not cached
        if mode == "docker":
            docker_config = global_config.get("docker", {})
            instance = DockerSandbox(config=docker_config)
            SandboxFactory._instances[mode] = instance
            return instance
            
        elif mode == "tmux":
            tmux_config = global_config.get("tmux", {})
            instance = TmuxSandbox(event_bus=event_bus, config=tmux_config)
            SandboxFactory._instances[mode] = instance
            return instance
            
        else:
            raise ValueError(f"Unsupported sandbox mode: {mode}")

