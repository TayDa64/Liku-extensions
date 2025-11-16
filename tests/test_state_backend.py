#!/usr/bin/env python3
"""
Unit tests for state_backend.py
"""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from state_backend import StateBackend


class StateBackendTests(unittest.TestCase):
    """Test StateBackend functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.backend = StateBackend(str(self.db_path))
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'backend'):
            self.backend.close()
    
    def test_database_initialization(self):
        """Test database is initialized with correct schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {
            'agent_session', 'tmux_pane', 'event_log',
            'guidance', 'approval_settings', 'schema_version'
        }
        
        self.assertTrue(expected_tables.issubset(tables))
        conn.close()
    
    def test_wal_mode_enabled(self):
        """Test WAL mode is enabled for concurrency."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        
        self.assertEqual(mode.lower(), 'wal')
        conn.close()
    
    def test_start_session(self):
        """Test starting an agent session."""
        session_key = self.backend.start_session(
            agent_name="test-agent",
            pane_id="%1",
            config={"key": "value"}
        )
        
        self.assertIsNotNone(session_key)
        self.assertTrue(session_key.startswith("test-agent-"))
        
        # Verify session was recorded
        sessions = self.backend.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["agent_name"], "test-agent")
        self.assertEqual(sessions[0]["pane_id"], "%1")
    
    def test_end_session(self):
        """Test ending an agent session."""
        session_key = self.backend.start_session("test-agent")
        
        # End session
        self.backend.end_session(session_key, exit_code=0)
        
        # Verify session is marked as ended
        sessions = self.backend.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertIsNotNone(sessions[0]["ended_at"])
        self.assertEqual(sessions[0]["exit_code"], 0)
    
    def test_get_active_sessions(self):
        """Test getting only active sessions."""
        # Start two sessions
        session1 = self.backend.start_session("agent1")
        session2 = self.backend.start_session("agent2")
        
        # End one session
        self.backend.end_session(session1, exit_code=0)
        
        # Get active sessions
        active = self.backend.get_sessions(active_only=True)
        
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["session_key"], session2)
    
    def test_log_event(self):
        """Test logging an event."""
        session_key = self.backend.start_session("test-agent")
        
        event_id = self.backend.log_event(
            event_type="agent.spawn",
            payload={"agent": "test-agent"},
            session_key=session_key,
            agent_name="test-agent"
        )
        
        self.assertIsNotNone(event_id)
        
        # Verify event was recorded
        events = self.backend.get_events(limit=1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "agent.spawn")
        self.assertEqual(events[0]["payload"]["agent"], "test-agent")
    
    def test_get_events_with_filter(self):
        """Test filtering events by type."""
        session_key = self.backend.start_session("test-agent")
        
        # Log multiple event types
        self.backend.log_event("agent.spawn", {"num": 1}, session_key)
        self.backend.log_event("agent.kill", {"num": 2}, session_key)
        self.backend.log_event("agent.spawn", {"num": 3}, session_key)
        
        # Filter by type
        spawn_events = self.backend.get_events(event_type="agent.spawn")
        
        self.assertEqual(len(spawn_events), 2)
        self.assertTrue(all(e["type"] == "agent.spawn" for e in spawn_events))
    
    def test_get_events_with_limit(self):
        """Test limiting number of events returned."""
        session_key = self.backend.start_session("test-agent")
        
        # Log many events
        for i in range(10):
            self.backend.log_event(f"test.event{i}", {"num": i}, session_key)
        
        # Get limited results
        events = self.backend.get_events(limit=5)
        
        self.assertEqual(len(events), 5)
    
    def test_register_pane(self):
        """Test registering a tmux pane."""
        session_key = self.backend.start_session("test-agent", pane_id="%1")
        
        self.backend.register_pane(
            pane_id="%1",
            session_name="test-session",
            agent_name="test-agent",
            session_key=session_key
        )
        
        # Verify pane was registered
        panes = self.backend.get_panes()
        self.assertEqual(len(panes), 1)
        self.assertEqual(panes[0]["pane_id"], "%1")
        self.assertEqual(panes[0]["session_name"], "test-session")
    
    def test_unregister_pane(self):
        """Test unregistering a tmux pane."""
        session_key = self.backend.start_session("test-agent", pane_id="%1")
        self.backend.register_pane("%1", "test-session", "test-agent", session_key)
        
        # Unregister pane
        self.backend.unregister_pane("%1")
        
        # Verify pane is marked as inactive
        panes = self.backend.get_panes()
        self.assertEqual(len(panes), 1)
        self.assertIsNotNone(panes[0]["unregistered_at"])
    
    def test_set_approval_mode(self):
        """Test setting approval mode for an agent."""
        self.backend.set_approval_mode("test-agent", "ask")
        
        # Verify mode was set
        mode = self.backend.get_approval_mode("test-agent")
        self.assertEqual(mode, "ask")
    
    def test_get_approval_mode_default(self):
        """Test getting default approval mode."""
        mode = self.backend.get_approval_mode("nonexistent-agent")
        self.assertEqual(mode, "ask")  # Default mode
    
    def test_create_guidance(self):
        """Test creating a guidance record."""
        session_key = self.backend.start_session("test-agent")
        
        guidance_id = self.backend.create_guidance(
            agent_name="test-agent",
            session_key=session_key,
            prompt="Test prompt",
            response="Test response"
        )
        
        self.assertIsNotNone(guidance_id)
        
        # Verify guidance was recorded
        guidances = self.backend.get_guidances(agent_name="test-agent")
        self.assertEqual(len(guidances), 1)
        self.assertEqual(guidances[0]["prompt"], "Test prompt")
        self.assertEqual(guidances[0]["response"], "Test response")
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        import threading
        
        def create_session(agent_num):
            session_key = self.backend.start_session(f"agent-{agent_num}")
            self.backend.log_event("test.event", {"num": agent_num}, session_key)
        
        # Create multiple threads
        threads = [threading.Thread(target=create_session, args=(i,)) for i in range(10)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all sessions and events were recorded
        sessions = self.backend.get_sessions()
        events = self.backend.get_events()
        
        self.assertEqual(len(sessions), 10)
        self.assertEqual(len(events), 10)


if __name__ == "__main__":
    unittest.main()
