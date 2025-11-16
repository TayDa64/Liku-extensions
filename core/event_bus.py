#!/usr/bin/env python3
"""
Python implementation of the LIKU event bus.
Replaces event-bus.sh with better error handling and validation.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional

from state_backend import StateBackend


class EventBus:
    """
    Event bus for publishing and subscribing to LIKU events.
    Supports both JSONL file-based events and SQLite storage.
    """
    
    def __init__(self, events_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        """
        Initialize event bus.
        
        Args:
            events_dir: Directory for JSONL event files (default: ~/.liku/state/events)
            db_path: Path to SQLite database (default: ~/.liku/db/liku.db)
        """
        home = Path.home()
        self.events_dir = Path(events_dir) if events_dir else home / ".liku" / "state" / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)
        
        # Optional SQLite backend for structured storage
        self.db: Optional[StateBackend] = None
        if db_path or (home / ".liku" / "db" / "liku.db").exists():
            db_file = Path(db_path) if db_path else home / ".liku" / "db" / "liku.db"
            try:
                self.db = StateBackend(str(db_file))
            except Exception as e:
                print(f"Warning: Could not connect to state backend: {e}")
    
    def emit(
        self,
        event_type: str,
        payload: Any = None,
        session_key: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> str:
        """
        Emit an event to the bus.
        
        Args:
            event_type: Type of event (e.g., 'agent.spawn')
            payload: Event payload (dict, str, or None)
            session_key: Optional session key
            agent_name: Optional agent name
            
        Returns:
            Path to the created event file
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        # Normalize payload
        if payload is None:
            payload_json = "null"
        elif isinstance(payload, dict):
            payload_json = json.dumps(payload)
        elif isinstance(payload, str):
            # Check if already JSON
            if payload.strip().startswith('{') or payload.strip().startswith('['):
                payload_json = payload
            else:
                payload_json = json.dumps(payload)
        else:
            payload_json = json.dumps(str(payload))
        
        # Create event structure
        event = {
            "ts": timestamp,
            "type": event_type,
            "payload": json.loads(payload_json)
        }
        
        # Write to JSONL file
        event_file = self.events_dir / f"{int(time.time() * 1e9)}.event"
        with open(event_file, 'w') as f:
            json.dump(event, f)
            f.write('\n')
        
        # Also store in SQLite if available
        if self.db:
            try:
                self.db.log_event(
                    event_type=event_type,
                    payload=event["payload"],
                    session_key=session_key,
                    agent_name=agent_name
                )
            except Exception as e:
                print(f"Warning: Could not log event to database: {e}")
        
        return str(event_file)
    
    def stream(self, follow: bool = True) -> Iterator[Dict[str, Any]]:
        """
        Stream events from the bus.
        
        Args:
            follow: If True, continuously watch for new events
            
        Yields:
            Event dictionaries
        """
        # First, yield existing events
        for event_file in sorted(self.events_dir.glob("*.event")):
            if event_file.is_file():
                try:
                    with open(event_file) as f:
                        event = json.load(f)
                        yield event
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Warning: Could not read event {event_file}: {e}")
        
        if not follow:
            return
        
        # Watch for new events
        try:
            from watcher_factory import WatcherFactory
            
            factory = WatcherFactory(debounce_window=0.1)
            for watch_event in factory.watch(str(self.events_dir), recursive=False):
                if watch_event.path.endswith('.event'):
                    try:
                        with open(watch_event.path) as f:
                            event = json.load(f)
                            yield event
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"Warning: Could not read event {watch_event.path}: {e}")
        
        except ImportError:
            print("Warning: WatcherFactory not available, using polling")
            # Fallback to polling
            import time
            last_seen = set(f.name for f in self.events_dir.glob("*.event"))
            
            while True:
                time.sleep(1)
                current = set(f.name for f in self.events_dir.glob("*.event"))
                new_files = current - last_seen
                
                for filename in sorted(new_files):
                    event_file = self.events_dir / filename
                    try:
                        with open(event_file) as f:
                            event = json.load(f)
                            yield event
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"Warning: Could not read event {event_file}: {e}")
                
                last_seen = current
    
    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Dict[str, Any]], None],
        follow: bool = True
    ):
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: Type of event to subscribe to (or '*' for all)
            callback: Function to call for each matching event
            follow: If True, continuously watch for new events
        """
        for event in self.stream(follow=follow):
            if event_type == '*' or event.get('type') == event_type:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error in event callback: {e}")
    
    def get_recent_events(self, event_type: Optional[str] = None, limit: int = 100) -> list:
        """
        Get recent events from SQLite backend.
        
        Args:
            event_type: Optional event type filter
            limit: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        if not self.db:
            # Fallback to reading from files
            events = []
            for event_file in sorted(self.events_dir.glob("*.event"))[-limit:]:
                try:
                    with open(event_file) as f:
                        event = json.load(f)
                        if event_type is None or event.get('type') == event_type:
                            events.append(event)
                except (json.JSONDecodeError, IOError):
                    continue
            return events
        
        return self.db.get_events(event_type=event_type, limit=limit)


def main():
    """CLI entry point for event bus operations."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  event_bus.py emit <type> [payload]")
        print("  event_bus.py stream")
        print("  event_bus.py subscribe <type>")
        sys.exit(1)
    
    bus = EventBus()
    command = sys.argv[1]
    
    if command == "emit":
        if len(sys.argv) < 3:
            print("Usage: event_bus.py emit <type> [payload]")
            sys.exit(1)
        
        event_type = sys.argv[2]
        payload = sys.argv[3] if len(sys.argv) > 3 else None
        
        event_file = bus.emit(event_type, payload)
        print(f"Event emitted: {event_file}")
    
    elif command == "stream":
        print("Streaming events (Ctrl+C to stop)...")
        try:
            for event in bus.stream(follow=True):
                print(json.dumps(event))
        except KeyboardInterrupt:
            print("\nStopped streaming.")
    
    elif command == "subscribe":
        if len(sys.argv) < 3:
            print("Usage: event_bus.py subscribe <type>")
            sys.exit(1)
        
        event_type = sys.argv[2]
        print(f"Subscribing to {event_type} events (Ctrl+C to stop)...")
        
        def print_event(event: Dict[str, Any]):
            print(json.dumps(event))
        
        try:
            bus.subscribe(event_type, print_event, follow=True)
        except KeyboardInterrupt:
            print("\nStopped subscribing.")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
