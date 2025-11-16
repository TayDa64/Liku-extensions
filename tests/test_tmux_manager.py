#!/usr/bin/env python3
"""
Unit tests for tmux_manager.py
"""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from tmux_manager import TmuxManager, TmuxPane, TmuxSession


class TmuxManagerTests(unittest.TestCase):
    """Test TmuxManager functionality."""
    
    @patch('subprocess.run')
    def test_check_tmux_available(self, mock_run):
        """Test checking tmux availability."""
        mock_run.return_value = MagicMock(returncode=0, stdout="tmux 3.0")
        
        # Should not raise
        manager = TmuxManager()
        self.assertIsNotNone(manager)
    
    @patch('subprocess.run')
    def test_check_tmux_not_available(self, mock_run):
        """Test error when tmux not available."""
        mock_run.side_effect = FileNotFoundError()
        
        with self.assertRaises(RuntimeError):
            TmuxManager()
    
    @patch('subprocess.run')
    def test_list_sessions(self, mock_run):
        """Test listing tmux sessions."""
        # Mock tmux -V check
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        
        # Mock list-sessions output
        sessions_output = MagicMock(
            returncode=0,
            stdout="session1|2|1|1234567890\nsession2|3|0|1234567891\n"
        )
        
        mock_run.side_effect = [version_check, sessions_output]
        
        manager = TmuxManager()
        sessions = manager.list_sessions()
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].name, "session1")
        self.assertEqual(sessions[0].windows, 2)
        self.assertTrue(sessions[0].attached)
        self.assertEqual(sessions[1].name, "session2")
        self.assertFalse(sessions[1].attached)
    
    @patch('subprocess.run')
    def test_list_sessions_empty(self, mock_run):
        """Test listing sessions when none exist."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        sessions_output = MagicMock(returncode=1, stderr="no server running")
        
        mock_run.side_effect = [version_check, sessions_output]
        
        manager = TmuxManager()
        sessions = manager.list_sessions()
        
        self.assertEqual(len(sessions), 0)
    
    @patch('subprocess.run')
    def test_list_panes(self, mock_run):
        """Test listing tmux panes."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        
        panes_output = MagicMock(
            returncode=0,
            stdout="session1|0|0|%1|1234|bash|80|24\nsession1|0|1|%2|1235|vim|80|24\n"
        )
        
        mock_run.side_effect = [version_check, panes_output]
        
        manager = TmuxManager()
        panes = manager.list_panes()
        
        self.assertEqual(len(panes), 2)
        self.assertEqual(panes[0].session, "session1")
        self.assertEqual(panes[0].pane_id, "%1")
        self.assertEqual(panes[0].pane_pid, 1234)
        self.assertEqual(panes[0].pane_current_command, "bash")
        self.assertEqual(panes[1].pane_id, "%2")
        self.assertEqual(panes[1].pane_current_command, "vim")
    
    @patch('subprocess.run')
    def test_create_pane(self, mock_run):
        """Test creating a tmux pane."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        
        # Mock split-window command
        split_output = MagicMock(returncode=0, stdout="%3\n")
        
        # Mock list-panes to get created pane details
        panes_output = MagicMock(
            returncode=0,
            stdout="session1|0|2|%3|1236|bash|80|12\n"
        )
        
        mock_run.side_effect = [version_check, split_output, panes_output]
        
        manager = TmuxManager()
        pane = manager.create_pane("session1", command="bash", agent_name="test-agent")
        
        self.assertEqual(pane.pane_id, "%3")
        self.assertEqual(pane.pane_pid, 1236)
    
    @patch('subprocess.run')
    def test_kill_pane(self, mock_run):
        """Test killing a tmux pane."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        kill_output = MagicMock(returncode=0, stdout="")
        
        mock_run.side_effect = [version_check, kill_output]
        
        manager = TmuxManager()
        manager.kill_pane("%1", agent_name="test-agent")
        
        # Verify kill-pane was called
        self.assertEqual(mock_run.call_count, 2)
        kill_call = mock_run.call_args_list[1][0][0]
        self.assertIn("kill-pane", kill_call)
        self.assertIn("%1", kill_call)
    
    @patch('subprocess.run')
    def test_send_keys(self, mock_run):
        """Test sending keys to a pane."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        send_output = MagicMock(returncode=0, stdout="")
        
        mock_run.side_effect = [version_check, send_output]
        
        manager = TmuxManager()
        manager.send_keys("%1", "echo hello")
        
        # Verify send-keys was called
        send_call = mock_run.call_args_list[1][0][0]
        self.assertIn("send-keys", send_call)
        self.assertIn("%1", send_call)
        self.assertIn("echo hello", send_call)
    
    @patch('subprocess.run')
    def test_capture_pane(self, mock_run):
        """Test capturing pane output."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        capture_output = MagicMock(
            returncode=0,
            stdout="line1\nline2\nline3\n"
        )
        
        mock_run.side_effect = [version_check, capture_output]
        
        manager = TmuxManager()
        output = manager.capture_pane("%1")
        
        self.assertEqual(output, "line1\nline2\nline3")
    
    @patch('subprocess.run')
    def test_ensure_session_creates_new(self, mock_run):
        """Test ensuring session creates new one."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        list_output = MagicMock(returncode=0, stdout="")
        new_session_output = MagicMock(returncode=0, stdout="")
        
        mock_run.side_effect = [version_check, list_output, new_session_output]
        
        manager = TmuxManager()
        created = manager.ensure_session("new-session")
        
        self.assertTrue(created)
    
    @patch('subprocess.run')
    def test_ensure_session_already_exists(self, mock_run):
        """Test ensuring session when it already exists."""
        version_check = MagicMock(returncode=0, stdout="tmux 3.0")
        list_output = MagicMock(
            returncode=0,
            stdout="existing-session|1|0|1234567890\n"
        )
        
        mock_run.side_effect = [version_check, list_output]
        
        manager = TmuxManager()
        created = manager.ensure_session("existing-session")
        
        self.assertFalse(created)


if __name__ == "__main__":
    unittest.main()
