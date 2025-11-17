"""
Pytest tests for TmuxManager module.
Migrated from unittest to pytest with fixtures and mocking.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from tmux_manager import TmuxManager, TmuxPane, TmuxSession


@pytest.fixture
def mock_subprocess(mocker):
    """Mock subprocess.run for all tests."""
    return mocker.patch('subprocess.run')


@pytest.fixture
def tmux_manager_with_mocks(mock_subprocess):
    """Create TmuxManager with mocked subprocess."""
    # Mock tmux version check
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="tmux 3.0")
    return TmuxManager()


class TestTmuxManagerInit:
    """Test TmuxManager initialization."""
    
    def test_check_tmux_available(self, mock_subprocess):
        """Test checking tmux availability."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="tmux 3.0")
        
        manager = TmuxManager()
        assert manager is not None
    
    def test_check_tmux_not_available(self, mock_subprocess):
        """Test error when tmux not available."""
        mock_subprocess.side_effect = FileNotFoundError()
        
        with pytest.raises(RuntimeError, match="tmux not found"):
            TmuxManager()


class TestTmuxManagerSessions:
    """Test tmux session management."""
    
    def test_list_sessions(self, mock_subprocess):
        """Test listing tmux sessions."""
        # Mock tmux -V check
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        
        # Mock list-sessions output
        sessions_output = MagicMock(
            returncode=0,
            stdout="session1|2|1|1234567890\nsession2|3|0|1234567891\n"
        )
        
        mock_subprocess.side_effect = [version_check, sessions_output]
        
        manager = TmuxManager()
        sessions = manager.list_sessions()
        
        assert len(sessions) == 2
        assert sessions[0].name == "session1"
        assert sessions[0].windows == 2
        assert sessions[0].attached is True
        assert sessions[1].name == "session2"
        assert sessions[1].attached is False
    
    def test_list_sessions_empty(self, mock_subprocess):
        """Test listing sessions when none exist."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        sessions_output = MagicMock(returncode=1, stderr="no server running")
        
        mock_subprocess.side_effect = [version_check, sessions_output]
        
        manager = TmuxManager()
        sessions = manager.list_sessions()
        
        assert len(sessions) == 0
    
    def test_ensure_session_exists(self, tmux_manager_with_mocks, mock_subprocess):
        """Test ensuring a session exists."""
        # Mock session check (session doesn't exist)
        session_check = MagicMock(returncode=1)
        # Mock session creation
        session_create = MagicMock(returncode=0)
        
        mock_subprocess.side_effect = [session_check, session_create]
        
        tmux_manager_with_mocks.ensure_session("test-session")
        
        # Verify new-session was called
        assert mock_subprocess.call_count == 2


class TestTmuxManagerPanes:
    """Test tmux pane management."""
    
    def test_list_panes(self, mock_subprocess):
        """Test listing tmux panes."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        
        panes_output = MagicMock(
            returncode=0,
            stdout="session1:0.0|/bin/bash|80x24|%0|1|1234567890\n"
                   "session1:0.1|python|80x24|%1|0|1234567891\n"
        )
        
        mock_subprocess.side_effect = [version_check, panes_output]
        
        manager = TmuxManager()
        panes = manager.list_panes()
        
        assert len(panes) == 2
        assert panes[0].terminal_id == "session1:0.0"
        assert panes[0].command == "/bin/bash"
        assert panes[0].size == "80x24"
        assert panes[0].pane_id == "%0"
        assert panes[0].active is True
        assert panes[1].active is False
    
    def test_list_panes_empty(self, mock_subprocess):
        """Test listing panes when none exist."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        panes_output = MagicMock(returncode=1, stderr="no panes")
        
        mock_subprocess.side_effect = [version_check, panes_output]
        
        manager = TmuxManager()
        panes = manager.list_panes()
        
        assert len(panes) == 0
    
    def test_create_pane(self, tmux_manager_with_mocks, mock_subprocess):
        """Test creating a new pane."""
        # Mock split-window output
        split_output = MagicMock(returncode=0, stdout="%5")
        mock_subprocess.return_value = split_output
        
        pane_id = tmux_manager_with_mocks.create_pane(
            session="test-session",
            window="test-window",
            name="test-pane"
        )
        
        assert pane_id == "%5"
        # Verify split-window was called
        mock_subprocess.assert_called()
    
    def test_kill_pane(self, tmux_manager_with_mocks, mock_subprocess):
        """Test killing a pane."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        tmux_manager_with_mocks.kill_pane("%5")
        
        # Verify kill-pane was called with correct pane ID
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "kill-pane" in call_args
        assert "%5" in call_args


class TestTmuxManagerCommands:
    """Test tmux command execution."""
    
    def test_send_keys(self, tmux_manager_with_mocks, mock_subprocess):
        """Test sending keys to a pane."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        tmux_manager_with_mocks.send_keys("%5", "echo hello")
        
        # Verify send-keys was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "send-keys" in call_args
        assert "%5" in call_args
        assert "echo hello" in call_args
    
    def test_capture_pane(self, tmux_manager_with_mocks, mock_subprocess):
        """Test capturing pane output."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="captured output\n"
        )
        
        output = tmux_manager_with_mocks.capture_pane("%5")
        
        assert output == "captured output\n"
        # Verify capture-pane was called
        mock_subprocess.assert_called()
        call_args = mock_subprocess.call_args[0][0]
        assert "capture-pane" in call_args
        assert "%5" in call_args


class TestTmuxManagerOrphanedPanes:
    """Test orphaned pane detection."""
    
    @pytest.mark.requires_tmux
    def test_get_orphaned_panes_requires_psutil(self, tmux_manager_with_mocks, mock_subprocess):
        """Test orphaned pane detection with psutil."""
        # This test requires psutil and is mostly integration
        # Mock the panes list
        panes_output = MagicMock(
            returncode=0,
            stdout="session1:0.0|bash|80x24|%0|1|1234567890|1234\n"
        )
        mock_subprocess.return_value = panes_output
        
        # Try to get orphaned panes
        try:
            orphaned = tmux_manager_with_mocks.get_orphaned_panes()
            # If psutil available, should return a list
            assert isinstance(orphaned, list)
        except ImportError:
            # If psutil not available, that's OK for this test
            pytest.skip("psutil not available")


class TestTmuxManagerEventEmission:
    """Test event emission integration."""
    
    def test_create_pane_emits_event(self, mock_subprocess, mocker):
        """Test that creating a pane emits an event."""
        # Mock tmux version check
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        # Mock split-window
        split_output = MagicMock(returncode=0, stdout="%5")
        mock_subprocess.side_effect = [version_check, split_output]
        
        # Create manager with mock event bus
        mock_event_bus = mocker.MagicMock()
        manager = TmuxManager(event_bus=mock_event_bus)
        
        manager.create_pane(session="test", window="0", name="test-pane")
        
        # Verify event was emitted
        mock_event_bus.emit.assert_called_once()
        call_args = mock_event_bus.emit.call_args[0]
        assert call_args[0] == "pane.created"


# Integration tests (require tmux)
@pytest.mark.requires_tmux
class TestTmuxManagerIntegration:
    """Integration tests requiring actual tmux."""
    
    def test_real_tmux_check(self):
        """Test with real tmux if available."""
        try:
            manager = TmuxManager()
            # If tmux is available, this should work
            sessions = manager.list_sessions()
            assert isinstance(sessions, list)
        except RuntimeError:
            pytest.skip("tmux not available")
