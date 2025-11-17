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

from liku.state_backend import StateBackend


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
        """Test creating an agent session."""
        # create_agent_session requires session_key parameter
        session_key = "test-agent-12345"
        session_id = self.backend.create_agent_session(
            agent_name="test-agent",
            session_key=session_key,
            terminal_id="%1",
            mode="interactive"
        )
        
        self.assertIsNotNone(session_id)
        self.assertIsInstance(session_id, int)
        
        # Verify session was recorded
        sessions = self.backend.list_agent_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["agent_name"], "test-agent")
        self.assertEqual(sessions[0]["terminal_id"], "%1")
    
    def test_end_session(self):
        """Test ending an agent session."""
        session_key = "test-agent-12345"
        self.backend.create_agent_session("test-agent", session_key)
        
        # Update session status
        self.backend.update_agent_status("test-agent", session_key, "completed")
        
        # Verify session status was updated
        session = self.backend.get_agent_session("test-agent", session_key)
        self.assertIsNotNone(session)
        self.assertEqual(session["status"], "completed")
    
    def test_get_active_sessions(self):
        """Test getting only active sessions."""
        # Create two sessions
        session1 = "agent1-12345"
        session2 = "agent2-67890"
        self.backend.create_agent_session("agent1", session1)
        self.backend.create_agent_session("agent2", session2)
        
        # Mark one as completed
        self.backend.update_agent_status("agent1", session1, "completed")
        
        # Get active sessions (status='active')
        active = self.backend.list_agent_sessions(status="active")
        
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["session_key"], session2)
    
    def test_log_event(self):
        """Test logging an event."""
        session_key = "test-agent-12345"
        self.backend.create_agent_session("test-agent", session_key)
        
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
        self.assertEqual(events[0]["event_type"], "agent.spawn")
        self.assertEqual(events[0]["payload"]["agent"], "test-agent")
    
    def test_get_events_with_filter(self):
        """Test filtering events by type."""
        session_key = "test-agent-12345"
        self.backend.create_agent_session("test-agent", session_key)
        
        # Log multiple event types
        self.backend.log_event("agent.spawn", {"num": 1}, session_key)
        self.backend.log_event("agent.kill", {"num": 2}, session_key)
        self.backend.log_event("agent.spawn", {"num": 3}, session_key)
        
        # Filter by type
        spawn_events = self.backend.get_events(event_type="agent.spawn")
        
        self.assertEqual(len(spawn_events), 2)
        self.assertTrue(all(e["event_type"] == "agent.spawn" for e in spawn_events))
    
    def test_get_events_with_limit(self):
        """Test limiting number of events returned."""
        session_key = "test-agent-12345"
        self.backend.create_agent_session("test-agent", session_key)
        
        # Log many events
        for i in range(20):
            self.backend.log_event("test.event", {"num": i}, session_key)
        
        # Get limited events
        events = self.backend.get_events(limit=5)
        
        self.assertEqual(len(events), 5)
    
    def test_register_pane(self):
        """Test recording a tmux pane."""
        session_key = "test-agent-12345"
        self.backend.create_agent_session("test-agent", session_key, terminal_id="%1")
        
        pane_id = self.backend.record_pane(
            session_key=session_key,
            terminal_id="%1",
            pane_pid=1234,
            status="active"
        )
        
        # Verify pane was recorded
        panes = self.backend.list_panes()
        self.assertEqual(len(panes), 1)
        self.assertEqual(panes[0]["terminal_id"], "%1")
        self.assertEqual(panes[0]["session_key"], session_key)
    
    def test_unregister_pane(self):
        """Test marking a pane as closed."""
        session_key = "test-agent-12345"
        self.backend.create_agent_session("test-agent", session_key, terminal_id="%1")
        self.backend.record_pane(session_key, "%1", pane_pid=1234, status="active")
        
        # Mark as closed
        self.backend.record_pane(session_key, "%1", pane_pid=1234, status="closed")
        
        # Verify pane status updated
        pane = self.backend.get_pane("%1")
        self.assertIsNotNone(pane)
        self.assertEqual(pane["status"], "closed")
    
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
        session_key = "test-agent-12345"
        self.backend.create_agent_session("test-agent", session_key)
        
        guidance_id = self.backend.add_guidance(
            agent_name="test-agent",
            session_key=session_key,
            instructions="Test prompt",
            context="Test context"
        )
        
        self.assertIsNotNone(guidance_id)
        
        # Verify guidance was recorded
        guidances = self.backend.get_guidance(agent_name="test-agent")
        self.assertEqual(len(guidances), 1)
        self.assertEqual(guidances[0]["instructions"], "Test prompt")
        self.assertEqual(guidances[0]["context"], "Test context")

    def test_get_agent_session_by_pane_id(self):
        """Test getting an agent session by its pane ID (terminal_id)."""
        active_session_key = "test-agent-by-pane-123"
        active_terminal_id = "%99"
        inactive_session_key = "inactive-session"
        inactive_terminal_id = "%100"
        
        # Create an active session associated with a terminal_id
        self.backend.create_agent_session(
            agent_name="pane-agent",
            session_key=active_session_key,
            terminal_id=active_terminal_id
        )
        
        # Create another session that will be marked as inactive
        self.backend.create_agent_session(
            agent_name="inactive-agent",
            session_key=inactive_session_key,
            terminal_id=inactive_terminal_id
        )
        # Mark the second session as completed
        self.backend.update_agent_status("inactive-agent", inactive_session_key, "completed")

        # Retrieve the session by pane ID
        session = self.backend.get_agent_session_by_pane_id(active_terminal_id)
        
        self.assertIsNotNone(session)
        self.assertEqual(session["agent_name"], "pane-agent")
        self.assertEqual(session["session_key"], active_session_key)
        
        # Test that a non-existent pane_id returns None
        non_existent = self.backend.get_agent_session_by_pane_id("%-1")
        self.assertIsNone(non_existent)
        
        # Test that an inactive pane_id returns None
        inactive = self.backend.get_agent_session_by_pane_id(inactive_terminal_id)
        self.assertIsNone(inactive)
    
    def test_thread_safety(self):
        """Test thread-safe operations."""
        import threading
        
        def create_session(agent_num):
            session_key = f"agent-{agent_num}-12345"
            self.backend.create_agent_session(f"agent-{agent_num}", session_key)
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
        sessions = self.backend.list_agent_sessions()
        events = self.backend.get_events()
        
        self.assertEqual(len(sessions), 10)
        self.assertEqual(len(events), 10)


if __name__ == "__main__":
    unittest.main()
