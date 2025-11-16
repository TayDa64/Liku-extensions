#!/usr/bin/env python3
"""
Unified LIKU API daemon.
Consolidates event-bus, state management, and tmux operations into a single service.
Exposes UNIX socket API for CLI clients and optional HTTP REST API.
"""

import json
import os
import socket
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from event_bus import EventBus
from state_backend import StateBackend
from tmux_manager import TmuxManager


class LikuDaemon:
    """
    Unified LIKU daemon service.
    Provides centralized API for all LIKU operations.
    """
    
    def __init__(
        self,
        socket_path: Optional[str] = None,
        db_path: Optional[str] = None,
        events_dir: Optional[str] = None
    ):
        """
        Initialize the LIKU daemon.
        
        Args:
            socket_path: Path to UNIX socket (default: ~/.liku/liku.sock)
            db_path: Path to SQLite database (default: ~/.liku/db/liku.db)
            events_dir: Directory for event files (default: ~/.liku/state/events)
        """
        home = Path.home()
        
        # Setup paths
        self.socket_path = socket_path or str(home / ".liku" / "liku.sock")
        self.db_path = db_path or str(home / ".liku" / "db" / "liku.db")
        self.events_dir = events_dir or str(home / ".liku" / "state" / "events")
        
        # Initialize components
        self.state_backend = StateBackend(self.db_path)
        self.event_bus = EventBus(events_dir=self.events_dir, db_path=self.db_path)
        self.tmux_manager = TmuxManager(event_bus=self.event_bus)
        
        # Server state
        self.running = False
        self.socket_server: Optional[socket.socket] = None
        
        print(f"LIKU Daemon initialized")
        print(f"  Socket: {self.socket_path}")
        print(f"  Database: {self.db_path}")
        print(f"  Events: {self.events_dir}")
    
    def start(self):
        """Start the daemon server."""
        # Remove existing socket if present
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Create UNIX socket
        self.socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket_server.bind(self.socket_path)
        self.socket_server.listen(5)
        
        # Set socket permissions
        os.chmod(self.socket_path, 0o600)
        
        self.running = True
        print(f"LIKU Daemon listening on {self.socket_path}")
        
        # Accept connections
        while self.running:
            try:
                client_socket, _ = self.socket_server.accept()
                
                # Handle client in separate thread
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                thread.start()
            
            except KeyboardInterrupt:
                print("\nShutting down daemon...")
                break
            except Exception as e:
                print(f"Error accepting connection: {e}")
        
        self.stop()
    
    def stop(self):
        """Stop the daemon server."""
        self.running = False
        
        if self.socket_server:
            self.socket_server.close()
        
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        print("LIKU Daemon stopped")
    
    def _handle_client(self, client_socket: socket.socket):
        """
        Handle a client connection.
        
        Args:
            client_socket: Connected client socket
        """
        try:
            # Receive request
            data = client_socket.recv(4096)
            if not data:
                return
            
            request = json.loads(data.decode())
            
            # Process request
            response = self._process_request(request)
            
            # Send response
            client_socket.sendall(json.dumps(response).encode())
        
        except json.JSONDecodeError as e:
            error_response = {"status": "error", "error": f"Invalid JSON: {e}"}
            client_socket.sendall(json.dumps(error_response).encode())
        
        except Exception as e:
            error_response = {"status": "error", "error": str(e)}
            client_socket.sendall(json.dumps(error_response).encode())
        
        finally:
            client_socket.close()
    
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a client request.
        
        Args:
            request: Request dictionary with 'action' and optional parameters
            
        Returns:
            Response dictionary
        """
        action = request.get("action")
        
        if not action:
            return {"status": "error", "error": "Missing 'action' field"}
        
        # Event bus operations
        if action == "emit_event":
            return self._emit_event(request)
        
        elif action == "get_events":
            return self._get_events(request)
        
        # Tmux operations
        elif action == "list_sessions":
            return self._list_sessions()
        
        elif action == "list_panes":
            return self._list_panes(request)
        
        elif action == "create_pane":
            return self._create_pane(request)
        
        elif action == "kill_pane":
            return self._kill_pane(request)
        
        elif action == "send_keys":
            return self._send_keys(request)
        
        elif action == "capture_pane":
            return self._capture_pane(request)
        
        # State operations
        elif action == "get_agent_sessions":
            return self._get_agent_sessions()
        
        elif action == "start_agent_session":
            return self._start_agent_session(request)
        
        elif action == "end_agent_session":
            return self._end_agent_session(request)
        
        elif action == "ping":
            return {"status": "ok", "message": "pong"}
        
        else:
            return {"status": "error", "error": f"Unknown action: {action}"}
    
    # Event bus handlers
    
    def _emit_event(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Emit an event."""
        event_type = request.get("event_type")
        payload = request.get("payload")
        session_key = request.get("session_key")
        agent_name = request.get("agent_name")
        
        if not event_type:
            return {"status": "error", "error": "Missing 'event_type'"}
        
        event_file = self.event_bus.emit(
            event_type=event_type,
            payload=payload,
            session_key=session_key,
            agent_name=agent_name
        )
        
        return {"status": "ok", "event_file": event_file}
    
    def _get_events(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Get recent events."""
        event_type = request.get("event_type")
        limit = request.get("limit", 100)
        
        events = self.event_bus.get_recent_events(event_type=event_type, limit=limit)
        
        return {"status": "ok", "events": events}
    
    # Tmux handlers
    
    def _list_sessions(self) -> Dict[str, Any]:
        """List tmux sessions."""
        sessions = self.tmux_manager.list_sessions()
        
        return {
            "status": "ok",
            "sessions": [
                {
                    "name": s.name,
                    "windows": s.windows,
                    "attached": s.attached,
                    "created": s.created
                }
                for s in sessions
            ]
        }
    
    def _list_panes(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """List tmux panes."""
        session = request.get("session")
        
        panes = self.tmux_manager.list_panes(session)
        
        return {
            "status": "ok",
            "panes": [
                {
                    "session": p.session,
                    "window_index": p.window_index,
                    "pane_index": p.pane_index,
                    "pane_id": p.pane_id,
                    "pane_pid": p.pane_pid,
                    "pane_current_command": p.pane_current_command,
                    "pane_width": p.pane_width,
                    "pane_height": p.pane_height
                }
                for p in panes
            ]
        }
    
    def _create_pane(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Create a tmux pane."""
        session = request.get("session")
        command = request.get("command")
        vertical = request.get("vertical", False)
        agent_name = request.get("agent_name")
        
        if not session:
            return {"status": "error", "error": "Missing 'session'"}
        
        pane = self.tmux_manager.create_pane(
            session=session,
            command=command,
            vertical=vertical,
            agent_name=agent_name
        )
        
        return {
            "status": "ok",
            "pane": {
                "pane_id": pane.pane_id,
                "pane_pid": pane.pane_pid
            }
        }
    
    def _kill_pane(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Kill a tmux pane."""
        pane_id = request.get("pane_id")
        agent_name = request.get("agent_name")
        
        if not pane_id:
            return {"status": "error", "error": "Missing 'pane_id'"}
        
        self.tmux_manager.kill_pane(pane_id=pane_id, agent_name=agent_name)
        
        return {"status": "ok"}
    
    def _send_keys(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send keys to a tmux pane."""
        pane_id = request.get("pane_id")
        keys = request.get("keys")
        literal = request.get("literal", False)
        
        if not pane_id or not keys:
            return {"status": "error", "error": "Missing 'pane_id' or 'keys'"}
        
        self.tmux_manager.send_keys(pane_id=pane_id, keys=keys, literal=literal)
        
        return {"status": "ok"}
    
    def _capture_pane(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Capture tmux pane output."""
        pane_id = request.get("pane_id")
        start = request.get("start", -50)
        
        if not pane_id:
            return {"status": "error", "error": "Missing 'pane_id'"}
        
        output = self.tmux_manager.capture_pane(pane_id=pane_id, start=start)
        
        return {"status": "ok", "output": output}
    
    # State handlers
    
    def _get_agent_sessions(self) -> Dict[str, Any]:
        """Get all agent sessions."""
        sessions = self.state_backend.get_sessions()
        
        return {"status": "ok", "sessions": sessions}
    
    def _start_agent_session(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Start an agent session."""
        agent_name = request.get("agent_name")
        pane_id = request.get("pane_id")
        config = request.get("config")
        
        if not agent_name:
            return {"status": "error", "error": "Missing 'agent_name'"}
        
        session_key = self.state_backend.start_session(
            agent_name=agent_name,
            pane_id=pane_id,
            config=config
        )
        
        return {"status": "ok", "session_key": session_key}
    
    def _end_agent_session(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """End an agent session."""
        session_key = request.get("session_key")
        exit_code = request.get("exit_code", 0)
        
        if not session_key:
            return {"status": "error", "error": "Missing 'session_key'"}
        
        self.state_backend.end_session(session_key=session_key, exit_code=exit_code)
        
        return {"status": "ok"}


def main():
    """Main entry point."""
    import sys
    
    daemon = LikuDaemon()
    
    try:
        daemon.start()
    except KeyboardInterrupt:
        print("\nInterrupted")
        daemon.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
