import docker
from docker.models.containers import Container
from docker.errors import ImageNotFound, NotFound
from pathlib import Path # Added import
from liku.sandbox.base import Sandbox, SandboxResource
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class DockerSandbox(Sandbox):
    """
    A sandbox implementation that uses Docker containers for execution.
    Each agent session runs within its own Docker container.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.client = docker.from_env()
        self.config = config or {}
        self.container_name_prefix = self.config.get("container_name_prefix", "liku-agent-")
        self.default_image = self.config.get("default_image", "ubuntu:latest")
        logger.info(f"DockerSandbox initialized with config: {self.config}")

    def create(
        self,
        agent_name: str,
        session_key: str,
        command: str,
        config: Dict[str, Any]
    ) -> SandboxResource:
        """
        Creates and starts a new Docker container for an agent session.
        """
        image = config.get("image", self.default_image)
        container_name = f"{self.container_name_prefix}{session_key}"
        
        try:
            # Pull image if not available locally
            self.client.images.pull(image)
        except ImageNotFound:
            logger.error(f"Docker image '{image}' not found.")
            raise
        except Exception as e:
            logger.error(f"Error pulling Docker image '{image}': {e}")
            raise

        try:
            # Get the project root dynamically
            project_root = Path(__file__).parent.parent.parent
            
            container = self.client.containers.run(
                image,
                command=command,
                name=container_name,
                detach=True,
                tty=True,  # Allocate a pseudo-TTY for interactive processes
                stdin_open=True, # Keep stdin open
                volumes={
                    str(project_root): {'bind': '/app', 'mode': 'ro'}
                },
                working_dir='/app' # Set working directory inside container
            )
            logger.info(f"Docker container '{container.id}' created for agent '{agent_name}' (session: {session_key})")
            return SandboxResource(id=container.id, pid=container.top()['Processes'][0][1] if container.top()['Processes'] else None)
        except Exception as e:
            logger.error(f"Error creating Docker container for agent '{agent_name}': {e}")
            raise

    def execute(self, resource_id: str, command: str, literal: bool = False) -> str:
        """
        Executes a command inside the specified Docker container.
        """
        try:
            container = self.client.containers.get(resource_id)
            # Use exec_run for commands within an already running container
            # If literal is True, execute the command as-is without shell interpretation
            if literal:
                exec_command = command
            else:
                # Wrap command in sh -c for consistent shell behavior
                exec_command = ["/bin/sh", "-c", command]
            
            exit_code, output = container.exec_run(exec_command, stream=False, demux=True)
            
            stdout = output[0].decode('utf-8') if output[0] else ""
            stderr = output[1].decode('utf-8') if output[1] else ""

            if exit_code != 0:
                logger.warning(f"Command '{command}' in container '{resource_id}' exited with code {exit_code}. Stderr: {stderr}")
                # Optionally raise an exception or return error status
                return f"Error (exit code {exit_code}): {stderr}\n{stdout}"
            
            return stdout + stderr # Return both stdout and stderr for exec_run
        except NotFound:
            logger.error(f"Docker container '{resource_id}' not found.")
            raise
        except Exception as e:
            logger.error(f"Error executing command '{command}' in container '{resource_id}': {e}")
            raise

    def kill(self, resource_id: str, agent_name: str):
        """
        Kills and removes the specified Docker container.
        """
        try:
            container = self.client.containers.get(resource_id)
            container.stop()
            container.remove()
            logger.info(f"Docker container '{resource_id}' for agent '{agent_name}' killed and removed.")
        except NotFound:
            logger.warning(f"Attempted to kill non-existent Docker container '{resource_id}'.")
        except Exception as e:
            logger.error(f"Error killing Docker container '{resource_id}': {e}")
            raise

    def capture_output(self, resource_id: str, lines: int = -1) -> str:
        """
        Captures the output from the specified Docker container.
        """
        try:
            container = self.client.containers.get(resource_id)
            # Use logs() to get container output. tail=lines for last N lines.
            output_bytes = container.logs(tail=lines, stream=False)
            return output_bytes.decode('utf-8')
        except NotFound:
            logger.error(f"Docker container '{resource_id}' not found.")
            raise
        except Exception as e:
            logger.error(f"Error capturing output from container '{resource_id}': {e}")
            raise