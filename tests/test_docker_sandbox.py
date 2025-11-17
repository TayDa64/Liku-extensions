import pytest
from unittest.mock import MagicMock, patch
from liku.sandbox.docker_backend import DockerSandbox
from liku.sandbox.base import SandboxResource
from docker.errors import ImageNotFound, NotFound, APIError

@pytest.fixture
def mock_docker_client():
    """Mocks the Docker client and its methods."""
    with patch('docker.from_env') as mock_from_env:
        mock_client_instance = MagicMock()
        
        # Mock client.images.pull
        mock_client_instance.images.pull.return_value = None # pull doesn't return anything specific
        
        # Mock client.containers.run
        mock_container_run_result = MagicMock()
        mock_container_run_result.id = "test_container_id"
        mock_container_run_result.top.return_value = {'Processes': [['root', '1234', '0.0', '0.0', '0', '0', '?', 'Ss', '0:00', 'sleep 10']]}
        mock_client_instance.containers.run.return_value = mock_container_run_result

        # Mock client.containers.get
        mock_container_get_result = MagicMock()
        mock_container_get_result.exec_run.return_value = (0, (b"stdout output", b"stderr output")) # Corrected exec_run return
        mock_container_get_result.logs.return_value = b"container logs\nline2"
        mock_client_instance.containers.get.return_value = mock_container_get_result
        
        mock_from_env.return_value = mock_client_instance
        yield mock_from_env, mock_client_instance # Yield both mock_from_env and mock_client_instance

@pytest.fixture
def docker_sandbox(mock_docker_client):
    """Provides a DockerSandbox instance with a mocked Docker client."""
    mock_from_env, mock_client_instance = mock_docker_client
    return DockerSandbox()

class TestDockerSandbox:
    """Tests for the DockerSandbox implementation."""

    def test_init(self, mock_docker_client):
        """Test that the Docker client is initialized."""
        mock_from_env, mock_client_instance = mock_docker_client
        sandbox = DockerSandbox()
        mock_from_env.assert_called_once()
        assert sandbox.client == mock_client_instance

    def test_create_container_success(self, docker_sandbox, mock_docker_client):
        """Test successful container creation."""
        mock_from_env, mock_client_instance = mock_docker_client
        
        resource = docker_sandbox.create(
            agent_name="test-agent",
            session_key="test-session",
            command="sleep 10",
            config={"image": "ubuntu:latest"}
        )
        
        mock_client_instance.images.pull.assert_called_once_with("ubuntu:latest")
        mock_client_instance.containers.run.assert_called_once_with(
            "ubuntu:latest",
            command="sleep 10",
            name="liku-agent-test-session",
            detach=True,
            tty=True,
            stdin_open=True
        )
        assert isinstance(resource, SandboxResource)
        assert resource.id == "test_container_id"
        assert resource.pid == "1234"

    def test_create_container_image_not_found(self, docker_sandbox, mock_docker_client):
        """Test container creation fails if image not found."""
        mock_from_env, mock_client_instance = mock_docker_client
        mock_client_instance.images.pull.side_effect = ImageNotFound("Image not found")
        
        with pytest.raises(ImageNotFound):
            docker_sandbox.create(
                agent_name="test-agent",
                session_key="test-session",
                command="sleep 10",
                config={"image": "nonexistent-image"}
            )
        mock_client_instance.images.pull.assert_called_once_with("nonexistent-image")
        mock_client_instance.containers.run.assert_not_called()

    def test_execute_command_success(self, docker_sandbox, mock_docker_client):
        """Test successful command execution inside a container."""
        mock_from_env, mock_client_instance = mock_docker_client
        
        output = docker_sandbox.execute("test_container_id", "ls -l")
        
        mock_client_instance.containers.get.assert_called_once_with("test_container_id")
        mock_client_instance.containers.get.return_value.exec_run.assert_called_once_with(["/bin/sh", "-c", "ls -l"], stream=False, demux=True)
        assert output == "stdout outputstderr output"

    def test_execute_command_literal(self, docker_sandbox, mock_docker_client):
        """Test successful literal command execution inside a container."""
        mock_from_env, mock_client_instance = mock_docker_client
        
        output = docker_sandbox.execute("test_container_id", "echo 'hello'", literal=True)
        
        mock_client_instance.containers.get.assert_called_once_with("test_container_id")
        mock_client_instance.containers.get.return_value.exec_run.assert_called_once_with("echo 'hello'", stream=False, demux=True)
        assert output == "stdout outputstderr output" # The fixture returns both stdout/stderr

    def test_execute_command_failure(self, docker_sandbox, mock_docker_client):
        """Test command execution failure inside a container."""
        mock_from_env, mock_client_instance = mock_docker_client
        mock_client_instance.containers.get.return_value.exec_run.return_value = (1, (b"stdout", b"error output"))
        
        output = docker_sandbox.execute("test_container_id", "bad-command")
        
        assert "Error (exit code 1): error output\nstdout" in output

    def test_execute_container_not_found(self, docker_sandbox, mock_docker_client):
        """Test command execution fails if container not found."""
        mock_from_env, mock_client_instance = mock_docker_client
        mock_client_instance.containers.get.side_effect = NotFound("Container not found")
        
        with pytest.raises(NotFound):
            docker_sandbox.execute("nonexistent_container", "ls")
        mock_client_instance.containers.get.assert_called_once_with("nonexistent_container")

    def test_kill_container_success(self, docker_sandbox, mock_docker_client):
        """Test successful container killing and removal."""
        mock_from_env, mock_client_instance = mock_docker_client
        
        docker_sandbox.kill("test_container_id", "test-agent")
        
        mock_client_instance.containers.get.assert_called_once_with("test_container_id")
        mock_client_instance.containers.get.return_value.stop.assert_called_once()
        mock_client_instance.containers.get.return_value.remove.assert_called_once()

    def test_kill_container_not_found(self, docker_sandbox, mock_docker_client):
        """Test killing a non-existent container."""
        mock_from_env, mock_client_instance = mock_docker_client
        mock_client_instance.containers.get.side_effect = NotFound("Container not found")
        
        docker_sandbox.kill("nonexistent_container", "test-agent")
        mock_client_instance.containers.get.assert_called_once_with("nonexistent_container")
        # No exception should be raised, just a warning logged

    def test_capture_output_success(self, docker_sandbox, mock_docker_client):
        """Test successful output capture from a container."""
        mock_from_env, mock_client_instance = mock_docker_client
        
        output = docker_sandbox.capture_output("test_container_id", lines=10)
        
        mock_client_instance.containers.get.assert_called_once_with("test_container_id")
        mock_client_instance.containers.get.return_value.logs.assert_called_once_with(tail=10, stream=False)
        assert output == "container logs\nline2"

    def test_capture_output_container_not_found(self, docker_sandbox, mock_docker_client):
        """Test output capture fails if container not found."""
        mock_from_env, mock_client_instance = mock_docker_client
        mock_client_instance.containers.get.side_effect = NotFound("Container not found")
        
        with pytest.raises(NotFound):
            docker_sandbox.capture_output("nonexistent_container")
        mock_client_instance.containers.get.assert_called_once_with("nonexistent_container")

    def test_create_container_no_pid(self, docker_sandbox, mock_docker_client):
        """Test container creation when top() returns no processes."""
        mock_from_env, mock_client_instance = mock_docker_client
        mock_client_instance.containers.run.return_value.id = "test_container_id_no_pid"
        mock_client_instance.containers.run.return_value.top.return_value = {'Processes': []} # No processes
        
        resource = docker_sandbox.create(
            agent_name="test-agent",
            session_key="test-session",
            command="sleep 10",
            config={"image": "ubuntu:latest"}
        )
        
        assert isinstance(resource, SandboxResource)
        assert resource.id == "test_container_id_no_pid"
        assert resource.pid is None
