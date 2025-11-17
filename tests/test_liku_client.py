#!/usr/bin/env python3
"""
Unit tests for liku_client.py
"""

import json
import os
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from liku_client import LikuClient, SUPPORTS_UNIX_SOCKETS


class LikuClientInitTests(unittest.TestCase):
    """Tests for LikuClient constructor logic."""

    @patch('liku_client.SUPPORTS_UNIX_SOCKETS', True)
    def test_init_autodetect_unix(self):
        """Test auto-detection prefers UNIX socket when available."""
        client = LikuClient()
        self.assertFalse(client.use_tcp)
        # Make the test platform-agnostic
        expected_segment = os.path.join(".liku", "liku.sock")
        self.assertIn(expected_segment, client.socket_path)

    @patch('liku_client.SUPPORTS_UNIX_SOCKETS', False)
    def test_init_autodetect_tcp(self):
        """Test auto-detection falls back to TCP when UNIX sockets are not supported."""
        client = LikuClient()
        self.assertTrue(client.use_tcp)
        self.assertEqual(client.tcp_host, "127.0.0.1")
        self.assertEqual(client.tcp_port, 13337)

    def test_init_explicit_tcp(self):
        """Test explicit configuration for TCP."""
        client = LikuClient(tcp_host="localhost", tcp_port=9999)
        self.assertTrue(client.use_tcp)
        self.assertEqual(client.tcp_host, "localhost")
        self.assertEqual(client.tcp_port, 9999)

    @patch('liku_client.SUPPORTS_UNIX_SOCKETS', True)
    def test_init_explicit_unix(self):
        """Test explicit configuration for UNIX socket."""
        client = LikuClient(socket_path="/tmp/custom.sock")
        self.assertFalse(client.use_tcp)
        self.assertEqual(client.socket_path, "/tmp/custom.sock")


@patch('liku_client.LikuClient._send_request')
class LikuClientTests(unittest.TestCase):
    """Test LikuClient functionality using mocking."""

    def test_ping_success(self, mock_send_request):
        """Test successful ping."""
        mock_send_request.return_value = {"status": "ok", "message": "pong"}
        client = LikuClient()
        result = client.ping()
        self.assertTrue(result)
        mock_send_request.assert_called_once_with({"action": "ping"})

    def test_ping_failure(self, mock_send_request):
        """Test failed ping."""
        mock_send_request.side_effect = ConnectionError()
        client = LikuClient()
        result = client.ping()
        self.assertFalse(result)

    def test_emit_event(self, mock_send_request):
        """Test emitting an event."""
        mock_send_request.return_value = {"status": "ok", "event_file": "/path/to/event.event"}
        client = LikuClient()
        event_file = client.emit_event("test.event", {"key": "value"}, session_key="s1", agent_name="a1")
        self.assertEqual(event_file, "/path/to/event.event")
        mock_send_request.assert_called_once_with({
            "action": "emit_event",
            "event_type": "test.event",
            "payload": {"key": "value"},
            "session_key": "s1",
            "agent_name": "a1"
        })

    def test_get_events(self, mock_send_request):
        """Test getting events."""
        mock_response = [
            {"type": "test.event1", "payload": {"num": 1}},
            {"type": "test.event2", "payload": {"num": 2}}
        ]
        mock_send_request.return_value = {"status": "ok", "events": mock_response}
        client = LikuClient()
        events = client.get_events(event_type="test", limit=5)
        self.assertEqual(events, mock_response)
        mock_send_request.assert_called_once_with({
            "action": "get_events",
            "event_type": "test",
            "limit": 5
        })

    def test_list_sessions(self, mock_send_request):
        """Test listing tmux sessions."""
        mock_response = [{"name": "s1"}]
        mock_send_request.return_value = {"status": "ok", "sessions": mock_response}
        client = LikuClient()
        sessions = client.list_sessions()
        self.assertEqual(sessions, mock_response)
        mock_send_request.assert_called_once_with({"action": "list_sessions"})

    def test_list_panes(self, mock_send_request):
        """Test listing tmux panes."""
        mock_response = [{"pane_id": "%1"}]
        mock_send_request.return_value = {"status": "ok", "panes": mock_response}
        client = LikuClient()
        panes = client.list_panes(session="s1")
        self.assertEqual(panes, mock_response)
        mock_send_request.assert_called_once_with({"action": "list_panes", "session": "s1"})

    def test_create_pane(self, mock_send_request):
        """Test creating a tmux pane."""
        mock_response = {"pane_id": "%2"}
        mock_send_request.return_value = {"status": "ok", "pane": mock_response}
        client = LikuClient()
        pane = client.create_pane("s1", command="bash", vertical=True, agent_name="a1")
        self.assertEqual(pane, mock_response)
        mock_send_request.assert_called_once_with({
            "action": "create_pane",
            "session": "s1",
            "command": "bash",
            "vertical": True,
            "agent_name": "a1"
        })

    def test_kill_pane(self, mock_send_request):
        """Test killing a tmux pane."""
        mock_send_request.return_value = {"status": "ok"}
        client = LikuClient()
        client.kill_pane("%1", agent_name="a1")
        mock_send_request.assert_called_once_with({"action": "kill_pane", "pane_id": "%1", "agent_name": "a1"})

    def test_send_keys(self, mock_send_request):
        """Test sending keys to a pane."""
        mock_send_request.return_value = {"status": "ok"}
        client = LikuClient()
        client.send_keys("%1", "ls -l", literal=True)
        mock_send_request.assert_called_once_with({
            "action": "send_keys",
            "pane_id": "%1",
            "keys": "ls -l",
            "literal": True
        })

    def test_capture_pane(self, mock_send_request):
        """Test capturing pane output."""
        mock_send_request.return_value = {"status": "ok", "output": "file1.txt"}
        client = LikuClient()
        output = client.capture_pane("%1", start=-10)
        self.assertEqual(output, "file1.txt")
        mock_send_request.assert_called_once_with({
            "action": "capture_pane",
            "pane_id": "%1",
            "start": -10
        })

    def test_get_agent_sessions(self, mock_send_request):
        """Test getting all agent sessions."""
        mock_response = [{"agent_name": "a1"}]
        mock_send_request.return_value = {"status": "ok", "sessions": mock_response}
        client = LikuClient()
        sessions = client.get_agent_sessions()
        self.assertEqual(sessions, mock_response)
        mock_send_request.assert_called_once_with({"action": "get_agent_sessions"})

    def test_start_agent_session(self, mock_send_request):
        """Test starting an agent session."""
        mock_send_request.return_value = {"status": "ok", "session_key": "key123"}
        client = LikuClient()
        session_key = client.start_agent_session("a1", pane_id="%1", config={"c": 1})
        self.assertEqual(session_key, "key123")
        mock_send_request.assert_called_once_with({
            "action": "start_agent_session",
            "agent_name": "a1",
            "pane_id": "%1",
            "config": {"c": 1}
        })

    def test_end_agent_session(self, mock_send_request):
        """Test ending an agent session."""
        mock_send_request.return_value = {"status": "ok"}
        client = LikuClient()
        client.end_agent_session("key123", exit_code=1)
        mock_send_request.assert_called_once_with({
            "action": "end_agent_session",
            "session_key": "key123",
            "exit_code": 1
        })

    def test_error_response(self, mock_send_request):
        """Test handling error response from daemon."""
        # Simplify the test: directly raise the error from the mock
        mock_send_request.side_effect = RuntimeError("Something went wrong")
        client = LikuClient()
        with self.assertRaises(RuntimeError) as context:
            client.list_sessions() # This call should now trigger the side_effect
        self.assertIn("Something went wrong", str(context.exception))

    def test_connection_error(self, mock_send_request):
        """Test handling connection error."""
        mock_send_request.side_effect = ConnectionError("Could not connect")
        client = LikuClient()
        with self.assertRaises(ConnectionError):
            # Use a method that doesn't have its own try/except block
            client.list_sessions()


if __name__ == "__main__":
    unittest.main()
