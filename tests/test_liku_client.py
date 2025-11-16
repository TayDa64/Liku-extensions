#!/usr/bin/env python3
"""
Unit tests for liku_client.py
"""

import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from liku_client import LikuClient


class LikuClientTests(unittest.TestCase):
    """Test LikuClient functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.socket_path = Path(self.temp_dir) / "test.sock"
        self.client = LikuClient(str(self.socket_path))
    
    def _mock_daemon_response(self, response):
        """Mock daemon response for testing."""
        def mock_connect(addr):
            pass
        
        def mock_sendall(data):
            pass
        
        def mock_recv(size):
            return json.dumps(response).encode()
        
        def mock_close():
            pass
        
        mock_socket = MagicMock()
        mock_socket.connect = mock_connect
        mock_socket.sendall = mock_sendall
        mock_socket.recv = mock_recv
        mock_socket.close = mock_close
        
        return mock_socket
    
    @patch('socket.socket')
    def test_ping_success(self, mock_socket_class):
        """Test successful ping."""
        mock_socket = self._mock_daemon_response({"status": "ok", "message": "pong"})
        mock_socket_class.return_value = mock_socket
        
        result = self.client.ping()
        
        self.assertTrue(result)
    
    @patch('socket.socket')
    def test_ping_failure(self, mock_socket_class):
        """Test failed ping."""
        mock_socket_class.side_effect = ConnectionRefusedError()
        
        result = self.client.ping()
        
        self.assertFalse(result)
    
    @patch('socket.socket')
    def test_emit_event(self, mock_socket_class):
        """Test emitting an event."""
        mock_socket = self._mock_daemon_response({
            "status": "ok",
            "event_file": "/path/to/event.event"
        })
        mock_socket_class.return_value = mock_socket
        
        event_file = self.client.emit_event("test.event", {"key": "value"})
        
        self.assertEqual(event_file, "/path/to/event.event")
    
    @patch('socket.socket')
    def test_get_events(self, mock_socket_class):
        """Test getting events."""
        mock_socket = self._mock_daemon_response({
            "status": "ok",
            "events": [
                {"type": "test.event1", "payload": {"num": 1}},
                {"type": "test.event2", "payload": {"num": 2}}
            ]
        })
        mock_socket_class.return_value = mock_socket
        
        events = self.client.get_events(limit=2)
        
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "test.event1")
    
    @patch('socket.socket')
    def test_list_sessions(self, mock_socket_class):
        """Test listing tmux sessions."""
        mock_socket = self._mock_daemon_response({
            "status": "ok",
            "sessions": [
                {"name": "session1", "windows": 2, "attached": True},
                {"name": "session2", "windows": 1, "attached": False}
            ]
        })
        mock_socket_class.return_value = mock_socket
        
        sessions = self.client.list_sessions()
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]["name"], "session1")
    
    @patch('socket.socket')
    def test_list_panes(self, mock_socket_class):
        """Test listing tmux panes."""
        mock_socket = self._mock_daemon_response({
            "status": "ok",
            "panes": [
                {"pane_id": "%1", "session": "session1", "pane_pid": 1234}
            ]
        })
        mock_socket_class.return_value = mock_socket
        
        panes = self.client.list_panes()
        
        self.assertEqual(len(panes), 1)
        self.assertEqual(panes[0]["pane_id"], "%1")
    
    @patch('socket.socket')
    def test_create_pane(self, mock_socket_class):
        """Test creating a tmux pane."""
        mock_socket = self._mock_daemon_response({
            "status": "ok",
            "pane": {"pane_id": "%2", "pane_pid": 1235}
        })
        mock_socket_class.return_value = mock_socket
        
        pane = self.client.create_pane("session1", command="bash")
        
        self.assertEqual(pane["pane_id"], "%2")
        self.assertEqual(pane["pane_pid"], 1235)
    
    @patch('socket.socket')
    def test_kill_pane(self, mock_socket_class):
        """Test killing a tmux pane."""
        mock_socket = self._mock_daemon_response({"status": "ok"})
        mock_socket_class.return_value = mock_socket
        
        # Should not raise
        self.client.kill_pane("%1")
    
    @patch('socket.socket')
    def test_start_agent_session(self, mock_socket_class):
        """Test starting an agent session."""
        mock_socket = self._mock_daemon_response({
            "status": "ok",
            "session_key": "test-agent-12345"
        })
        mock_socket_class.return_value = mock_socket
        
        session_key = self.client.start_agent_session("test-agent", pane_id="%1")
        
        self.assertEqual(session_key, "test-agent-12345")
    
    @patch('socket.socket')
    def test_error_response(self, mock_socket_class):
        """Test handling error response from daemon."""
        mock_socket = self._mock_daemon_response({
            "status": "error",
            "error": "Something went wrong"
        })
        mock_socket_class.return_value = mock_socket
        
        with self.assertRaises(RuntimeError) as context:
            self.client.emit_event("test.event")
        
        self.assertIn("Something went wrong", str(context.exception))
    
    def test_connection_error(self):
        """Test handling connection error."""
        with self.assertRaises(ConnectionError) as context:
            self.client.emit_event("test.event")
        
        self.assertIn("Cannot connect to LIKU daemon", str(context.exception))


if __name__ == "__main__":
    unittest.main()
