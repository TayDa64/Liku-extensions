#!/usr/bin/env python3
"""
Integration tests for full LIKU system.
Tests the interaction between daemon, client, event bus, state backend, and tmux manager.
"""

import json
import os
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
import socket

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))

from liku_client import LikuClient
from event_bus import EventBus
from state_backend import StateBackend


class LikuTestHarness:
    """Test harness for running LIKU system in test mode."""
    
    def __init__(self, test_dir: str):
        """
        Initialize test harness.
        
        Args:
            test_dir: Temporary directory for test artifacts
        """
        self.test_dir = Path(test_dir)
        self.db_path = self.test_dir / "liku.db"
        self.events_dir = self.test_dir / "events"
        self.events_dir.mkdir(exist_ok=True)
        
        self.daemon_process = None
        self.client = None
        self.db = None
        self.event_bus = None

        # Platform-aware communication setup
        self.use_tcp = not hasattr(socket, 'AF_UNIX')
        if self.use_tcp:
            self.tcp_host = "127.0.0.1"
            self.tcp_port = 13337
            self.socket_path = None
        else:
            self.socket_path = self.test_dir / "liku.sock"
            self.tcp_port = None
            self.tcp_host = None

    def start(self):
        """Start the LIKU daemon in test mode."""
        daemon_script = Path(__file__).parent.parent.parent / "core" / "liku_daemon.py"
        
        env = os.environ.copy()
        # Pass test-specific paths to the daemon
        env["LIKU_DB_PATH"] = str(self.db_path)
        env["LIKU_EVENTS_DIR"] = str(self.events_dir)
        if self.use_tcp:
            env["LIKU_USE_TCP"] = "1"
            env["LIKU_TCP_PORT"] = str(self.tcp_port)
        else:
            env["LIKU_SOCKET_PATH"] = str(self.socket_path)

        self.daemon_process = subprocess.Popen(
            [sys.executable, str(daemon_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.test_dir)
        )
        
        # Wait for daemon to start
        self._wait_for_daemon()
        
        # Initialize client and other components
        if self.use_tcp:
            self.client = LikuClient(tcp_host=self.tcp_host, tcp_port=self.tcp_port)
        else:
            self.client = LikuClient(socket_path=str(self.socket_path))
            
        self.db = StateBackend(str(self.db_path))
        self.event_bus = EventBus(events_dir=str(self.events_dir), db_path=str(self.db_path))

    def _wait_for_daemon(self):
        """Wait for the daemon to become ready."""
        max_wait = 5
        wait_interval = 0.1
        elapsed = 0
        
        ready = False
        while not ready and elapsed < max_wait:
            if self.use_tcp:
                # Poll TCP port
                try:
                    with socket.create_connection((self.tcp_host, self.tcp_port), timeout=wait_interval):
                        ready = True
                except (socket.timeout, ConnectionRefusedError):
                    time.sleep(wait_interval)
            else:
                # Check for UNIX socket file
                if self.socket_path.exists():
                    ready = True
                else:
                    time.sleep(wait_interval)
            
            elapsed += wait_interval

        if not ready:
            stdout, stderr = self.daemon_process.communicate()
            print("DAEMON STDOUT:", stdout.decode())
            print("DAEMON STDERR:", stderr.decode())
            raise RuntimeError("Daemon failed to start within timeout")

    def stop(self):
        """Stop the LIKU daemon."""
        if self.daemon_process:
            if self.use_tcp:
                self.daemon_process.terminate() # Use terminate on Windows
            else:
                self.daemon_process.send_signal(signal.SIGINT)
            
            try:
                self.daemon_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.daemon_process.kill()
        
        if self.db:
            self.db.close()


import shutil
import unittest

# ... (existing imports)

@unittest.skipUnless(shutil.which("tmux"), "tmux is not available in the system PATH")
class FullSystemTests(unittest.TestCase):
    """Integration tests for full LIKU system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.harness = LikuTestHarness(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self, 'harness'):
            self.harness.stop()
    
    @unittest.skip("Requires tmux - run manually in tmux environment")
    def test_full_agent_lifecycle(self):
        """Test complete agent lifecycle through the system."""
        self.harness.start()
        
        # Start agent session
        session_key = self.harness.client.start_agent_session(
            agent_name="test-agent",
            pane_id="%1",
            config={"test": True}
        )
        
        self.assertIsNotNone(session_key)
        
        # Emit event
        event_file = self.harness.client.emit_event(
            "agent.spawn",
            payload={"agent": "test-agent"},
            session_key=session_key,
            agent_name="test-agent"
        )
        
        self.assertIsNotNone(event_file)
        
        # Verify event was logged in database
        time.sleep(0.5)  # Allow time for event to be processed
        events = self.harness.db.get_events(event_type="agent.spawn")
        
        self.assertGreater(len(events), 0)
        self.assertEqual(events[0]["type"], "agent.spawn")
        
        # Verify session exists
        sessions = self.harness.db.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["agent_name"], "test-agent")
        
        # End session
        self.harness.client.end_agent_session(session_key, exit_code=0)
        
        # Verify session ended
        sessions = self.harness.db.get_sessions()
        self.assertIsNotNone(sessions[0]["ended_at"])
    
    def test_daemon_ping(self):
        """Test daemon responds to ping."""
        self.harness.start()
        
        result = self.harness.client.ping()
        self.assertTrue(result)
    
    def test_event_emission_and_retrieval(self):
        """Test emitting and retrieving events through daemon."""
        self.harness.start()
        
        # Emit multiple events
        for i in range(5):
            self.harness.client.emit_event(
                f"test.event{i}",
                payload={"num": i}
            )
        
        # Retrieve events
        time.sleep(0.5)
        events = self.harness.client.get_events(limit=10)
        
        self.assertGreaterEqual(len(events), 5)
    
    def test_event_bus_integration(self):
        """Test EventBus integrates correctly with StateBackend."""
        self.harness.start()
        
        # Emit event through event bus
        event_file = self.harness.event_bus.emit(
            "test.integration",
            payload={"source": "event_bus"}
        )
        
        # Verify event exists in both file and database
        self.assertTrue(Path(event_file).exists())
        
        time.sleep(0.5)
        db_events = self.harness.db.get_events(event_type="test.integration")
        
        self.assertGreater(len(db_events), 0)
        self.assertEqual(db_events[0]["payload"]["source"], "event_bus")
    
    @unittest.skip("Requires tmux - run manually in tmux environment")
    def test_tmux_integration(self):
        """Test tmux operations through daemon."""
        self.harness.start()
        
        # List sessions (should work even without tmux running)
        try:
            sessions = self.harness.client.list_sessions()
            self.assertIsInstance(sessions, list)
        except RuntimeError:
            # Expected if tmux not running
            pass
    
    def test_concurrent_operations(self):
        """Test concurrent operations through daemon."""
        import threading
        
        self.harness.start()
        
        def emit_events(thread_num):
            for i in range(10):
                self.harness.client.emit_event(
                    f"test.thread{thread_num}",
                    payload={"thread": thread_num, "num": i}
                )
        
        # Create multiple threads
        threads = [threading.Thread(target=emit_events, args=(i,)) for i in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all events were recorded
        time.sleep(1)
        events = self.harness.client.get_events(limit=100)
        
        self.assertGreaterEqual(len(events), 50)


if __name__ == "__main__":
    unittest.main()
