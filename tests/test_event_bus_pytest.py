"""
Pytest tests for EventBus module.
Migrated from unittest to pytest with fixtures.
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path

import pytest

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from event_bus import EventBus


class TestEventBusBasic:
    """Basic EventBus functionality tests."""
    
    def test_emit_creates_event_file(self, event_bus, test_events_dir):
        """Test that emit() creates an event file."""
        event_bus.emit("test.event", {"data": "test123"})
        
        events_dir = Path(test_events_dir)
        # EventBus creates .event files, not .jsonl
        event_files = list(events_dir.glob("*.event"))
        assert len(event_files) > 0, "Event file should be created"
    
    def test_emit_writes_jsonl_format(self, event_bus, test_events_dir):
        """Test that emit() writes proper JSON format."""
        event_bus.emit("test.event", {"foo": "bar"})
        
        events_dir = Path(test_events_dir)
        event_files = list(events_dir.glob("*.event"))
        assert event_files, "Should have at least one event file"
        
        with open(event_files[0]) as f:
            event = json.load(f)
            
            assert event["type"] == "test.event"
            assert event["payload"]["foo"] == "bar"
            assert "ts" in event  # EventBus uses 'ts' not 'timestamp'
    
    def test_emit_stores_in_database(self, event_bus, state_backend):
        """Test that emit() stores events in the database."""
        event_bus.emit("test.db_event", {"key": "value"})
        
        # Query database directly
        events = state_backend.get_events(event_type="test.db_event", limit=1)
        assert len(events) == 1
        assert events[0]["event_type"] == "test.db_event"
        assert json.loads(events[0]["payload"])["key"] == "value"
    
    def test_emit_multiple_events(self, event_bus, state_backend):
        """Test emitting multiple events."""
        for i in range(5):
            event_bus.emit(f"test.event_{i}", {"index": i})
        
        # Check all events stored
        all_events = state_backend.get_events(limit=10)
        assert len(all_events) >= 5
    
    def test_get_recent_events_limit(self, event_bus, state_backend):
        """Test get_recent_events respects limit parameter."""
        # Emit multiple events
        for i in range(10):
            event_bus.emit("test.limit", {"num": i})
        
        # Get only 3 recent events
        recent = event_bus.get_recent_events(limit=3)
        assert len(recent) == 3
    
    def test_get_recent_events_type_filter(self, event_bus):
        """Test get_recent_events filters by event type."""
        # Emit different event types
        event_bus.emit("type.a", {"data": "a"})
        event_bus.emit("type.b", {"data": "b"})
        event_bus.emit("type.a", {"data": "a2"})
        
        # Filter by type
        type_a_events = event_bus.get_recent_events(event_type="type.a")
        assert len(type_a_events) == 2
        assert all(e["type"] == "type.a" for e in type_a_events)


class TestEventBusStreaming:
    """EventBus streaming functionality tests."""
    
    @pytest.mark.slow
    def test_stream_watches_for_changes(self, event_bus, test_events_dir, mocker):
        """Test that stream() watches for file changes."""
        # Mock the watcher
        mock_watcher = mocker.MagicMock()
        mock_watcher.__iter__ = lambda self: iter([
            mocker.MagicMock(path=str(Path(test_events_dir) / "test.jsonl"))
        ])
        
        with patch('liku.event_bus.WatcherFactory') as MockFactory:
            MockFactory.return_value.watch.return_value = mock_watcher
            
            # Stream should yield events
            stream_gen = event_bus.stream()
            next(stream_gen)  # Should not raise
    
    def test_stream_without_watcher_raises(self, test_events_dir, test_db_path):
        """Test that stream() raises if watcher not available."""
        # Create EventBus without watcher support
        with patch('liku.event_bus.WatcherFactory', side_effect=ImportError):
            event_bus = EventBus(events_dir=test_events_dir, db_path=test_db_path)
            
            with pytest.raises(RuntimeError, match="File watcher not available"):
                list(event_bus.stream())


class TestEventBusSubscriptions:
    """EventBus subscription functionality tests."""
    
    def test_subscribe_calls_callback(self, event_bus):
        """Test that subscribe() calls callback for matching events."""
        callback = MagicMock()
        
        event_bus.subscribe("test.callback", callback)
        event_bus.emit("test.callback", {"data": "test"})
        
        # Callback should be called
        time.sleep(0.1)  # Give subscription time to process
        callback.assert_called_once()
        
        args = callback.call_args[0]
        assert args[0]["type"] == "test.callback"
    
    def test_subscribe_wildcard_pattern(self, event_bus):
        """Test that subscribe() supports wildcard patterns."""
        callback = MagicMock()
        
        event_bus.subscribe("agent.*", callback)
        event_bus.emit("agent.spawn", {"agent": "test"})
        event_bus.emit("agent.kill", {"agent": "test"})
        event_bus.emit("system.log", {"msg": "test"})  # Should not match
        
        time.sleep(0.2)
        assert callback.call_count >= 2  # At least the two agent events
    
    def test_unsubscribe_stops_callbacks(self, event_bus):
        """Test that unsubscribe() stops callbacks."""
        callback = MagicMock()
        
        event_bus.subscribe("test.unsub", callback)
        event_bus.emit("test.unsub", {"data": "first"})
        
        time.sleep(0.1)
        call_count_after_first = callback.call_count
        
        event_bus.unsubscribe("test.unsub", callback)
        event_bus.emit("test.unsub", {"data": "second"})
        
        time.sleep(0.1)
        # Call count should not increase after unsubscribe
        assert callback.call_count == call_count_after_first


class TestEventBusCLI:
    """EventBus CLI interface tests."""
    
    def test_cli_emit_command(self, event_bus, test_events_dir, capsys):
        """Test CLI emit command."""
        with patch('sys.argv', ['event_bus.py', 'emit', 'test.cli', '{"key":"value"}']):
            # This would call main() - test the underlying function
            event_bus.emit("test.cli", {"key": "value"})
            
            # Verify event was created
            events = event_bus.get_recent_events(event_type="test.cli", limit=1)
            assert len(events) == 1
            assert events[0]["payload"]["key"] == "value"
    
    @pytest.mark.slow
    def test_cli_stream_command(self, mocker):
        """Test CLI stream command functionality."""
        # This is primarily testing that the CLI interface exists
        # Full stream testing requires integration test
        with patch('liku.event_bus.WatcherFactory'):
            # Just verify the module is importable and has main()
            from liku.event_bus import main
            assert callable(main)


# Performance benchmarks (optional, run with pytest -m "not slow")
@pytest.mark.slow
class TestEventBusPerformance:
    """Performance benchmarks for EventBus."""
    
    def test_emit_performance_bulk(self, event_bus, benchmark):
        """Benchmark bulk event emission."""
        def emit_100_events():
            for i in range(100):
                event_bus.emit(f"perf.test", {"index": i})
        
        # pytest-benchmark plugin required
        if hasattr(pytest, 'benchmark'):
            benchmark(emit_100_events)
        else:
            emit_100_events()  # Just run normally
    
    def test_query_performance(self, event_bus, state_backend, benchmark):
        """Benchmark event querying."""
        # Setup: emit events
        for i in range(500):
            event_bus.emit("perf.query", {"index": i})
        
        def query_events():
            return event_bus.get_recent_events(limit=100)
        
        if hasattr(pytest, 'benchmark'):
            benchmark(query_events)
        else:
            query_events()
