#!/usr/bin/env python3
"""
Python client library for communicating with the LIKU daemon.
Provides high-level API for LIKU operations via UNIX socket or TCP.
"""

import json
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Platform detection for socket type
SUPPORTS_UNIX_SOCKETS = hasattr(socket, 'AF_UNIX')
DEFAULT_TCP_PORT = 13337


class LikuClient:
    """Client for interacting with the LIKU daemon."""

    def __init__(
        self,
        socket_path: Optional[str] = None,
        tcp_host: Optional[str] = None,
        tcp_port: Optional[int] = None,
        timeout: int = 10
    ):
        """
        Initialize the LIKU client.
        
        Args:
            socket_path: Path to UNIX socket (for Unix-like systems)
            tcp_host: Host for TCP connection (e.g., '127.0.0.1')
            tcp_port: Port for TCP connection
            timeout: Socket timeout in seconds
        """
        self.timeout = timeout
        
        # Determine connection mode
        if tcp_host and tcp_port:
            self.use_tcp = True
            self.tcp_host = tcp_host
            self.tcp_port = tcp_port
            self.socket_path = None
        elif socket_path:
            self.use_tcp = False
            self.socket_path = socket_path
            self.tcp_host = None
            self.tcp_port = None
        else:
            # Auto-detect default
            if SUPPORTS_UNIX_SOCKETS:
                self.use_tcp = False
                self.socket_path = str(Path.home() / ".liku" / "liku.sock")
            else:
                self.use_tcp = True
                self.tcp_host = "127.0.0.1"
                self.tcp_port = 13337

    def _get_socket(self) -> socket.socket:
        """Create and connect a socket based on the configured mode."""
        if self.use_tcp:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.tcp_host, self.tcp_port))
        else:
            if not self.socket_path or not Path(self.socket_path).exists():
                raise ConnectionError(f"UNIX socket not found at {self.socket_path}")
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
        return sock

    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a request to the daemon and get the response.
        
        Args:
            request: Request dictionary
            
        Returns:
            Response dictionary
        """
        try:
            with self._get_socket() as sock:
                sock.sendall(json.dumps(request).encode())
                
                # Receive response
                response_data = sock.recv(8192)
                if not response_data:
                    raise ConnectionError("Daemon closed the connection without a response.")
                
                response = json.loads(response_data.decode())
                
                if response.get("status") == "error":
                    raise RuntimeError(f"Daemon error: {response.get('error', 'Unknown error')}")
                
                return response
        
        except (ConnectionRefusedError, FileNotFoundError):
            endpoint = f"{self.tcp_host}:{self.tcp_port}" if self.use_tcp else self.socket_path
            raise ConnectionError(f"Could not connect to LIKU daemon at {endpoint}. Is it running?")
        except json.JSONDecodeError:
            raise ValueError("Failed to decode JSON response from daemon.")
        except Exception as e:
            raise e
    
    # Event bus operations
    
    def emit_event(
        self,
        event_type: str,
        payload: Any = None,
        session_key: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> str:
        """
        Emit an event.
        
        Args:
            event_type: Type of event
            payload: Event payload
            session_key: Optional session key
            agent_name: Optional agent name
            
        Returns:
            Path to created event file
        """
        response = self._send_request({
            "action": "emit_event",
            "event_type": event_type,
            "payload": payload,
            "session_key": session_key,
            "agent_name": agent_name
        })
        
        return response["event_file"]
    
    def get_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get recent events.
        
        Args:
            event_type: Optional event type filter
            limit: Maximum number of events
            
        Returns:
            List of event dictionaries
        """
        response = self._send_request({
            "action": "get_events",
            "event_type": event_type,
            "limit": limit
        })
        
        return response["events"]
    
    # Tmux operations
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List tmux sessions.
        
        Returns:
            List of session dictionaries
        """
        response = self._send_request({"action": "list_sessions"})
        return response["sessions"]
    
    def list_panes(self, session: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List tmux panes.
        
        Args:
            session: Optional session filter
            
        Returns:
            List of pane dictionaries
        """
        response = self._send_request({
            "action": "list_panes",
            "session": session
        })
        
        return response["panes"]
    
    def create_pane(
        self,
        session: str,
        command: Optional[str] = None,
        vertical: bool = False,
        agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a tmux pane.
        
        Args:
            session: Session name
            command: Optional command to run
            vertical: Split vertically if True
            agent_name: Optional agent name
            
        Returns:
            Pane dictionary with pane_id and pane_pid
        """
        response = self._send_request({
            "action": "create_pane",
            "session": session,
            "command": command,
            "vertical": vertical,
            "agent_name": agent_name
        })
        
        return response["pane"]
    
    def kill_pane(self, pane_id: str, agent_name: Optional[str] = None):
        """
        Kill a tmux pane.
        
        Args:
            pane_id: Pane ID to kill
            agent_name: Optional agent name
        """
        self._send_request({
            "action": "kill_pane",
            "pane_id": pane_id,
            "agent_name": agent_name
        })
    
    def send_keys(self, pane_id: str, keys: str, literal: bool = False):
        """
        Send keys to a tmux pane.
        
        Args:
            pane_id: Target pane ID
            keys: Keys to send
            literal: Send literally if True
        """
        self._send_request({
            "action": "send_keys",
            "pane_id": pane_id,
            "keys": keys,
            "literal": literal
        })
    
    def capture_pane(self, pane_id: str, start: int = -50) -> str:
        """
        Capture pane output.
        
        Args:
            pane_id: Pane ID to capture
            start: Starting line number
            
        Returns:
            Captured output
        """
        response = self._send_request({
            "action": "capture_pane",
            "pane_id": pane_id,
            "start": start
        })
        
        return response["output"]
    
    # State operations
    
    def get_agent_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all agent sessions.
        
        Returns:
            List of session dictionaries
        """
        response = self._send_request({"action": "get_agent_sessions"})
        return response["sessions"]
    
    def start_agent_session(
        self,
        agent_name: str,
        pane_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start an agent session.
        
        Args:
            agent_name: Name of agent
            pane_id: Optional pane ID
            config: Optional configuration
            
        Returns:
            Session key
        """
        response = self._send_request({
            "action": "start_agent_session",
            "agent_name": agent_name,
            "pane_id": pane_id,
            "config": config
        })
        
        return response["session_key"]
    
    def end_agent_session(self, session_key: str, exit_code: int = 0):
        """
        End an agent session.
        
        Args:
            session_key: Session key to end
            exit_code: Exit code
        """
        self._send_request({
            "action": "end_agent_session",
            "session_key": session_key,
            "exit_code": exit_code
        })
    
    def ping(self) -> bool:
        """
        Ping the daemon.
        
        Returns:
            True if daemon is responsive
        """
        try:
            response = self._send_request({"action": "ping"})
            return response.get("message") == "pong"
        except (ConnectionError, RuntimeError):
            return False


def main():
    """CLI entry point for client operations."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  liku_client.py ping")
        print("  liku_client.py list-sessions")
        print("  liku_client.py list-panes")
        print("  liku_client.py emit <event_type> [payload]")
        sys.exit(1)
    
    client = LikuClient()
    command = sys.argv[1]
    
    try:
        if command == "ping":
            if client.ping():
                print("Daemon is running")
            else:
                print("Daemon is not responding")
                sys.exit(1)
        
        elif command == "list-sessions":
            sessions = client.list_sessions()
            for session in sessions:
                print(f"{session['name']}: {session['windows']} windows, attached={session['attached']}")
        
        elif command == "list-panes":
            panes = client.list_panes()
            for pane in panes:
                print(f"{pane['pane_id']} ({pane['session']}:{pane['window_index']}.{pane['pane_index']}) - {pane['pane_current_command']}")
        
        elif command == "emit":
            if len(sys.argv) < 3:
                print("Usage: liku_client.py emit <event_type> [payload]")
                sys.exit(1)
            
            event_type = sys.argv[2]
            payload = sys.argv[3] if len(sys.argv) > 3 else None
            
            event_file = client.emit_event(event_type, payload)
            print(f"Event emitted: {event_file}")
        
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    
    except ConnectionError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
