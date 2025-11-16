#!/usr/bin/env python3
"""
Unit tests for event_bus.py
"""

import json
import tempfile
import time
import unittest
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from event_bus import EventBus


class EventBusTests(unittest.TestCase):
    """Test EventBus functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.events_dir = Path(self.temp_dir) / "events"
        self.bus = EventBus(events_dir=self.events_dir, db_path=None)
    
    def test_emit_simple_event(self):
        """Test emitting a simple event."""
        event_file = self.bus.emit("test.event", {"key": "value"})
        
        # Verify file exists
        self.assertTrue(Path(event_file).exists())
        
        # Verify content
        with open(event_file) as f:
            event = json.load(f)
        
        self.assertEqual(event["type"], "test.event")
        self.assertEqual(event["payload"]["key"], "value")
        self.assertIn("ts", event)
    
    def test_emit_with_string_payload(self):
        """Test emitting event with string payload."""
        event_file = self.bus.emit("test.event", "simple string")
        
        with open(event_file) as f:
            event = json.load(f)
        
        self.assertEqual(event["payload"], "simple string")
    
    def test_emit_with_json_string_payload(self):
        """Test emitting event with JSON string payload."""
        json_payload = '{"nested": "object"}'
        event_file = self.bus.emit("test.event", json_payload)
        
        with open(event_file) as f:
            event = json.load(f)
        
        self.assertEqual(event["payload"]["nested"], "object")
    
    def test_emit_with_null_payload(self):
        """Test emitting event with null payload."""
        event_file = self.bus.emit("test.event", None)
        
        with open(event_file) as f:
            event = json.load(f)
        
        self.assertIsNone(event["payload"])
    
    def test_stream_existing_events(self):
        """Test streaming existing events."""
        # Create multiple events
        self.bus.emit("test.event1", {"num": 1})
        time.sleep(0.01)
        self.bus.emit("test.event2", {"num": 2})
        time.sleep(0.01)
        self.bus.emit("test.event3", {"num": 3})
        
        # Stream without follow
        events = list(self.bus.stream(follow=False))
        
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["type"], "test.event1")
        self.assertEqual(events[1]["type"], "test.event2")
        self.assertEqual(events[2]["type"], "test.event3")
    
    def test_get_recent_events_no_db(self):
        """Test getting recent events without database."""
        # Create events
        for i in range(5):
            self.bus.emit(f"test.event{i}", {"num": i})
            time.sleep(0.01)
        
        # Get recent events
        events = self.bus.get_recent_events(limit=3)
        
        self.assertEqual(len(events), 3)
        # Should be most recent
        self.assertEqual(events[0]["type"], "test.event2")
        self.assertEqual(events[1]["type"], "test.event3")
        self.assertEqual(events[2]["type"], "test.event4")
    
    def test_get_recent_events_with_filter(self):
        """Test filtering events by type."""
        # Create mixed events
        self.bus.emit("agent.spawn", {"agent": "test"})
        self.bus.emit("agent.kill", {"agent": "test"})
        self.bus.emit("agent.spawn", {"agent": "test2"})
        time.sleep(0.01)
        
        # Filter by type
        events = self.bus.get_recent_events(event_type="agent.spawn")
        
        # Without DB, should filter from files
        spawn_events = [e for e in events if e["type"] == "agent.spawn"]
        self.assertEqual(len(spawn_events), 2)


class EventBusSubscriptionTests(unittest.TestCase):
    """Test EventBus subscription functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.events_dir = Path(self.temp_dir) / "events"
        self.bus = EventBus(events_dir=self.events_dir, db_path=None)
    
    def test_subscribe_existing_events(self):
        """Test subscribing to existing events."""
        # Create events first
        self.bus.emit("test.event", {"num": 1})
        self.bus.emit("test.event", {"num": 2})
        
        # Subscribe without follow
        received = []
        
        def callback(event):
            received.append(event)
            if len(received) >= 2:
                raise StopIteration()
        
        try:
            self.bus.subscribe("test.event", callback, follow=False)
        except StopIteration:
            pass
        
        self.assertEqual(len(received), 2)
        self.assertEqual(received[0]["payload"]["num"], 1)
        self.assertEqual(received[1]["payload"]["num"], 2)
    
    def test_subscribe_wildcard(self):
        """Test subscribing to all events with wildcard."""
        self.bus.emit("test.event1", {"num": 1})
        self.bus.emit("test.event2", {"num": 2})
        self.bus.emit("other.event", {"num": 3})
        
        received = []
        
        def callback(event):
            received.append(event)
            if len(received) >= 3:
                raise StopIteration()
        
        try:
            self.bus.subscribe("*", callback, follow=False)
        except StopIteration:
            pass
        
        self.assertEqual(len(received), 3)


if __name__ == "__main__":
    unittest.main()
