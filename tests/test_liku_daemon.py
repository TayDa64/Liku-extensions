import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import os

from liku.liku_daemon import LikuDaemon
from liku.sandbox.base import SandboxResource

@pytest.fixture
def mock_daemon(tmp_path, mocker):
    """Fixture to create a LikuDaemon instance with mocked dependencies."""
    mocker.patch('liku.liku_daemon.StateBackend')
    mocker.patch('liku.liku_daemon.EventBus')
    
    # Mock the factory to return a specific mock sandbox instance
    mock_sandbox_instance = MagicMock()
    mock_factory = mocker.patch('liku.liku_daemon.SandboxFactory')
    mock_factory.get_sandbox.return_value = mock_sandbox_instance

    # Mock the TmuxSandbox directly for the list_* methods that use it
    mock_tmux_sandbox_instance = MagicMock()
    mock_tmux_sandbox = mocker.patch('liku.liku_daemon.TmuxSandbox')
    mock_tmux_sandbox.return_value = mock_tmux_sandbox_instance

    # Mock Path methods that create directories
    mocker.patch.object(Path, 'mkdir')

    # Set env vars for predictability
    os.environ["LIKU_USE_TCP"] = "1"
    os.environ["LIKU_TCP_PORT"] = "12345"
    os.environ["LIKU_DB_PATH"] = str(tmp_path / "db/test.db")
    os.environ["LIKU_EVENTS_DIR"] = str(tmp_path / "events")

    daemon = LikuDaemon()
    # Attach mocks to the daemon instance for easy access in tests
    daemon.mock_sandbox = mock_sandbox_instance
    daemon.mock_tmux_sandbox = mock_tmux_sandbox_instance
    
    # Clean up env vars after test
    yield daemon
    del os.environ["LIKU_USE_TCP"]
    del os.environ["LIKU_TCP_PORT"]
    del os.environ["LIKU_DB_PATH"]
    del os.environ["LIKU_EVENTS_DIR"]


def test_init_configures_tcp(mock_daemon):
    """Test that daemon initializes in TCP mode correctly."""
    assert mock_daemon.use_tcp is True
    assert mock_daemon.tcp_port == 12345
    assert mock_daemon.socket_path is None

@patch('liku.liku_daemon.SUPPORTS_UNIX_SOCKETS', True)
def test_init_configures_unix(tmp_path, mocker):
    """Test that daemon initializes in UNIX socket mode correctly."""
    mocker.patch('liku.liku_daemon.StateBackend')
    mocker.patch('liku.liku_daemon.EventBus')
    mocker.patch('liku.liku_daemon.SandboxFactory')
    mocker.patch('liku.liku_daemon.TmuxSandbox')
    mocker.patch.object(Path, 'mkdir')

    socket_path = str(tmp_path / "test.sock")
    os.environ["LIKU_USE_TCP"] = "0"
    os.environ["LIKU_SOCKET_PATH"] = socket_path
    
    daemon = LikuDaemon()
    
    assert daemon.use_tcp is False
    assert daemon.socket_path == socket_path
    assert daemon.tcp_port is None
    
    del os.environ["LIKU_USE_TCP"]
    del os.environ["LIKU_SOCKET_PATH"]

def test_process_request_no_action(mock_daemon):
    """Test that a request with no action returns an error."""
    request = {"params": "some_value"}
    response = mock_daemon._process_request(request)
    assert response["status"] == "error"
    assert "Missing 'action'" in response["error"]

def test_process_request_unknown_action(mock_daemon):
    """Test that a request with an unknown action returns an error."""
    request = {"action": "non_existent_action"}
    response = mock_daemon._process_request(request)
    assert response["status"] == "error"
    assert "Unknown action" in response["error"]

def test_ping_action(mock_daemon):
    """Test the 'ping' action."""
    request = {"action": "ping"}
    response = mock_daemon._process_request(request)
    assert response["status"] == "ok"
    assert response["message"] == "pong"

# === Event Bus Handlers ===

def test_emit_event_action(mock_daemon):
    """Test the 'emit_event' action."""
    request = {
        "action": "emit_event",
        "event_type": "test.event",
        "payload": {"data": "value"}
    }
    mock_daemon.event_bus.emit.return_value = "path/to/event.jsonl"
    
    response = mock_daemon._process_request(request)
    
    mock_daemon.event_bus.emit.assert_called_once_with(
        event_type="test.event",
        payload={"data": "value"},
        session_key=None,
        agent_name=None
    )
    assert response["status"] == "ok"
    assert response["event_file"] == "path/to/event.jsonl"

def test_get_events_action(mock_daemon):
    """Test the 'get_events' action."""
    request = {"action": "get_events", "limit": 50}
    mock_daemon.event_bus.get_recent_events.return_value = [{"event": "1"}]
    
    response = mock_daemon._process_request(request)
    
    mock_daemon.event_bus.get_recent_events.assert_called_once_with(
        event_type=None,
        limit=50
    )
    assert response["status"] == "ok"
    assert response["events"] == [{"event": "1"}]

# === Sandbox Handlers ===

def test_list_sessions_action(mock_daemon):
    """Test the 'list_sessions' action."""
    request = {"action": "list_sessions"}
    mock_session = MagicMock()
    mock_session.name = "test_session"
    mock_session.windows = 1
    mock_session.attached = 0
    mock_session.created = "sometime"
    mock_daemon.mock_tmux_sandbox.tmux_manager.list_sessions.return_value = [mock_session]
    
    response = mock_daemon._process_request(request)
    
    mock_daemon.mock_tmux_sandbox.tmux_manager.list_sessions.assert_called_once()
    assert response["status"] == "ok"
    assert len(response["sessions"]) == 1
    assert response["sessions"][0]["name"] == "test_session"

def test_create_pane_action(mock_daemon):
    """Test the 'create_pane' action (now uses sandbox)."""
    request = {
        "action": "create_pane",
        "agent_name": "test-agent",
        "session": "main",
        "command": "sleep 10"
    }
    mock_daemon.mock_sandbox.create.return_value = SandboxResource(id="%123", pid=4567)
    
    # Mock the agent config lookup
    mock_daemon.agent_configs = {"test-agent": {"some": "config"}}

    response = mock_daemon._process_request(request)
    
    # The daemon now correctly passes the looked-up agent config.
    # We check the important args and that config is a dict.
    mock_daemon.mock_sandbox.create.assert_called_once()
    call_args, call_kwargs = mock_daemon.mock_sandbox.create.call_args
    assert call_kwargs.get("agent_name") == "test-agent"
    assert call_kwargs.get("session_key") == "main"
    assert call_kwargs.get("command") == "sleep 10"
    assert isinstance(call_kwargs.get("config"), dict)
    assert call_kwargs.get("config") == {"some": "config"}

    assert response["status"] == "ok"
    assert response["pane"]["pane_id"] == "%123"

def test_kill_pane_action(mock_daemon):
    """Test the 'kill_pane' action (now uses sandbox)."""
    request = {"action": "kill_pane", "pane_id": "%123"}
    mock_daemon.state_backend.get_agent_session_by_pane_id.return_value = {"agent_name": "test-agent"}

    response = mock_daemon._process_request(request)
    
    mock_daemon.mock_sandbox.kill.assert_called_once_with(
        resource_id="%123",
        agent_name="test-agent"
    )
    assert response["status"] == "ok"

# === State Handlers ===

def test_start_agent_session_action(mock_daemon):
    """Test the 'start_agent_session' action."""
    request = {
        "action": "start_agent_session",
        "agent_name": "test-agent",
        "pane_id": "%456",
        "config": {"foo": "bar"}
    }
    mock_daemon.state_backend.start_session.return_value = "session-key-123"
    
    response = mock_daemon._process_request(request)
    
    mock_daemon.state_backend.start_session.assert_called_once_with(
        agent_name="test-agent",
        pane_id="%456",
        config={"foo": "bar"}
    )
    assert response["status"] == "ok"
    assert response["session_key"] == "session-key-123"

def test_end_agent_session_action(mock_daemon):
    """Test the 'end_agent_session' action."""
    request = {"action": "end_agent_session", "session_key": "key-123"}
    
    response = mock_daemon._process_request(request)
    
    mock_daemon.state_backend.end_session.assert_called_once_with(
        session_key="key-123",
        exit_code=0
    )
    assert response["status"] == "ok"

def test_get_agent_sessions_action(mock_daemon):
    """Test the 'get_agent_sessions' action."""
    request = {"action": "get_agent_sessions"}
    mock_daemon.state_backend.get_sessions.return_value = [{"session": "1"}]
    
    response = mock_daemon._process_request(request)
    
    mock_daemon.state_backend.get_sessions.assert_called_once()
    assert response["status"] == "ok"
    assert response["sessions"] == [{"session": "1"}]

# === Remaining Sandbox Handlers ===

def test_list_panes_action(mock_daemon):
    """Test the 'list_panes' action."""
    request = {"action": "list_panes", "session": "main"}
    mock_pane = MagicMock()
    mock_pane.session = "main"
    mock_pane.window_index = 0
    mock_pane.pane_index = 1
    mock_pane.pane_id = "%2"
    mock_pane.pane_pid = 9999
    mock_pane.pane_current_command = "bash"
    mock_pane.pane_width = 80
    mock_pane.pane_height = 24
    mock_daemon.mock_tmux_sandbox.tmux_manager.list_panes.return_value = [mock_pane]

    response = mock_daemon._process_request(request)

    mock_daemon.mock_tmux_sandbox.tmux_manager.list_panes.assert_called_once_with("main")
    assert response["status"] == "ok"
    assert len(response["panes"]) == 1
    assert response["panes"][0]["pane_id"] == "%2"

def test_send_keys_action(mock_daemon):
    """Test the 'send_keys' action with an allowed command."""
    # The 'test-agent' in the default config can run 'pytest'
    request = {"action": "send_keys", "pane_id": "%3", "keys": "pytest -v"}
    mock_daemon.state_backend.get_agent_session_by_pane_id.return_value = {"agent_name": "test-agent"}

    response = mock_daemon._process_request(request)

    mock_daemon.mock_sandbox.execute.assert_called_once_with(
        resource_id="%3",
        command="pytest -v",
        literal=False
    )
    assert response["status"] == "ok"

def test_capture_pane_action(mock_daemon):
    """Test the 'capture_pane' action."""
    request = {"action": "capture_pane", "pane_id": "%4", "start": -100}
    mock_daemon.state_backend.get_agent_session_by_pane_id.return_value = {"agent_name": "test-agent"}
    mock_daemon.mock_sandbox.capture_output.return_value = "some output"

    response = mock_daemon._process_request(request)

    mock_daemon.mock_sandbox.capture_output.assert_called_once_with(
        resource_id="%4",
        lines=100
    )
    assert response["status"] == "ok"
    assert response["output"] == "some output"

# === Error Condition Tests ===

@pytest.mark.parametrize("action, params", [
    ("emit_event", {"payload": {}}),
    ("create_pane", {"command": "c"}),
    ("kill_pane", {"agent_name": "a"}),
    ("send_keys", {"keys": "k"}),
    ("capture_pane", {"start": -10}),
    ("start_agent_session", {"pane_id": "p"}),
    ("end_agent_session", {"exit_code": 1}),
])
def test_actions_missing_required_params(mock_daemon, action, params):
    """Test that actions fail when required parameters are missing."""
    params["action"] = action
    response = mock_daemon._process_request(params)
    assert response["status"] == "error"
    assert "Missing" in response["error"]

def test_send_keys_missing_keys(mock_daemon):
    """Test send_keys fails if 'keys' is missing."""
    request = {"action": "send_keys", "pane_id": "%1"}
    response = mock_daemon._process_request(request)
    assert response["status"] == "error"
    assert "Missing 'pane_id' or 'keys'" in response["error"]


class TestDaemonSecurity:
    """Tests for the command validation security feature."""

    def test_send_keys_allowed_by_whitelist(self, mock_daemon):
        """Test a command that is on an agent's whitelist is allowed."""
        mock_daemon.agent_configs = {
            "build-agent": {
                "policies": {"allowed_commands": ["make", "npm"]}
            }
        }
        mock_daemon.global_policies = {}
        mock_daemon.state_backend.get_agent_session_by_pane_id.return_value = {
            "agent_name": "build-agent"
        }
        
        request = {"action": "send_keys", "pane_id": "%1", "keys": "make all"}
        response = mock_daemon._process_request(request)
        
        assert response["status"] == "ok"
        mock_daemon.mock_sandbox.execute.assert_called_once()

    def test_send_keys_denied_by_whitelist(self, mock_daemon):
        """Test a command that is not on an agent's whitelist is denied."""
        mock_daemon.agent_configs = {
            "build-agent": {
                "policies": {"allowed_commands": ["make", "npm"]}
            }
        }
        mock_daemon.global_policies = {}
        mock_daemon.state_backend.get_agent_session_by_pane_id.return_value = {
            "agent_name": "build-agent"
        }
        
        request = {"action": "send_keys", "pane_id": "%1", "keys": "pytest"}
        response = mock_daemon._process_request(request)
        
        assert response["status"] == "error"
        assert "Command denied by security policy" in response["error"]
        mock_daemon.mock_sandbox.execute.assert_not_called()

    def test_send_keys_denied_by_global_blacklist(self, mock_daemon):
        """Test a command that is on the global blacklist is denied."""
        mock_daemon.agent_configs = {}
        mock_daemon.global_policies = {"blocked_commands": ["sudo", "rm -rf"]}
        mock_daemon.state_backend.get_agent_session_by_pane_id.return_value = {
            "agent_name": "any-agent"
        }
        
        request = {"action": "send_keys", "pane_id": "%1", "keys": "sudo apt-get update"}
        response = mock_daemon._process_request(request)
        
        assert response["status"] == "error"
        assert "Command denied by security policy" in response["error"]
        mock_daemon.mock_sandbox.execute.assert_not_called()

    def test_send_keys_allowed_no_specific_policy(self, mock_daemon):
        """Test a command is allowed if the agent has no specific policy."""
        mock_daemon.agent_configs = {}
        mock_daemon.global_policies = {}
        mock_daemon.state_backend.get_agent_session_by_pane_id.return_value = {
            "agent_name": "unrestricted-agent"
        }
        
        request = {"action": "send_keys", "pane_id": "%1", "keys": "echo 'hello'"}
        response = mock_daemon._process_request(request)
        
        assert response["status"] == "ok"
        mock_daemon.mock_sandbox.execute.assert_called_once()