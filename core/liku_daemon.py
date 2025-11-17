#!/usr/bin/env python3
"""
Unified LIKU API daemon.
Consolidates event-bus, state management, and tmux operations into a single service.
Exposes UNIX socket API for CLI clients and optional HTTP REST API.
"""

import json
import os
import socket
import sys
import threading
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

from liku.event_bus import EventBus
from liku.state_backend import StateBackend
from liku.sandbox.factory import SandboxFactory
from liku.sandbox.tmux_backend import TmuxSandbox

# Platform detection for socket type
SUPPORTS_UNIX_SOCKETS = hasattr(socket, 'AF_UNIX')
DEFAULT_TCP_PORT = 13337


class LikuDaemon:
    """
    Unified LIKU daemon service.
    Provides centralized API for all LIKU operations.
    """
    
    def __init__(
        self,
        socket_path: Optional[str] = None,
        tcp_port: Optional[int] = None,
        db_path: Optional[str] = None,
        events_dir: Optional[str] = None,
        config_path: Optional[str] = None,
        use_tcp: bool = None
    ):
        """
        Initialize the LIKU daemon.
        
        Reads configuration from environment variables if available, otherwise uses
        defaults.
        
        Args:
            socket_path: Path to UNIX socket (overrides env var)
            tcp_port: TCP port for localhost communication (overrides env var)
            db_path: Path to SQLite database (overrides env var)
            events_dir: Directory for event files (overrides env var)
            config_path: Path to agents.yaml config file (overrides env var)
            use_tcp: Force TCP mode even on Unix platforms (overrides env var)
        """
        home = Path.home()

        # Determine communication mode from env or args
        if use_tcp is None:
            use_tcp_env = os.getenv("LIKU_USE_TCP", "auto")
            self.use_tcp = not SUPPORTS_UNIX_SOCKETS if use_tcp_env == "auto" else use_tcp_env == "1"
        else:
            self.use_tcp = use_tcp

        # Setup communication endpoint
        if self.use_tcp:
            self.tcp_port = tcp_port or int(os.getenv("LIKU_TCP_PORT", DEFAULT_TCP_PORT))
            self.tcp_host = "127.0.0.1"
            self.socket_path = None
            endpoint = f"TCP {self.tcp_host}:{self.tcp_port}"
        else:
            self.socket_path = socket_path or os.getenv("LIKU_SOCKET_PATH") or str(home / ".liku" / "liku.sock")
            self.tcp_port = None
            self.tcp_host = None
            endpoint = f"UNIX {self.socket_path}"

        # Setup paths from env or args
        self.db_path = db_path or os.getenv("LIKU_DB_PATH") or str(home / ".liku" / "db" / "liku.db")
        self.events_dir = events_dir or os.getenv("LIKU_EVENTS_DIR") or str(home / ".liku" / "state" / "events")
        self.config_path = config_path or os.getenv("LIKU_CONFIG_PATH") or str(Path(__file__).parent.parent / "config" / "agents.yaml")

        # Ensure directories exist
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.events_dir).mkdir(parents=True, exist_ok=True)

        # Load security policies
        self._load_agent_configs()

        # Initialize components
        self.state_backend = StateBackend(self.db_path)
        self.event_bus = EventBus(events_dir=self.events_dir, db_path=self.db_path)
        
        # Server state
        self.running = False
        self.socket_server: Optional[socket.socket] = None
        
        print(f"LIKU Daemon initialized")
        print(f"  Endpoint: {endpoint}")
        print(f"  Database: {self.db_path}")
        print(f"  Events: {self.events_dir}")
        print(f"  Config: {self.config_path}")

    def _load_agent_configs(self):
        """Load agent configurations and security policies from YAML file."""
        self.agent_configs: Dict[str, Any] = {}
        self.global_policies: Dict[str, Any] = {}
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f)
            
            self.global_policies = data.get("global_policies", {})
            
            agent_list = data.get("agents", [])
            for agent_config in agent_list:
                if "name" in agent_config:
                    self.agent_configs[agent_config["name"]] = agent_config

            print(f"Loaded {len(self.agent_configs)} agent configs and global policies.")

        except FileNotFoundError:
            print(f"Warning: Config file not found at {self.config_path}. No policies will be applied.")
        except (yaml.YAMLError, Exception) as e:
            print(f"Warning: Error parsing config file {self.config_path}: {e}. No policies will be applied.")

    def _is_command_allowed(self, agent_name: Optional[str], command: str) -> bool:
        """Check if a command is allowed by the security policies."""
        if not command:
            return True # Allowing empty commands

        # 1. Check against global blacklist
        blocked_commands = self.global_policies.get("blocked_commands", [])
        if any(command.strip().startswith(blocked) for blocked in blocked_commands):
            print(f"Security: Denied globally blocked command for agent '{agent_name}': {command}")
            return False

        # If there's no agent context, only global blacklist applies
        if not agent_name:
            return True

        # 2. Check against agent-specific whitelist
        agent_conf = self.agent_configs.get(agent_name)
        if not agent_conf:
            return True # No specific policy for this agent, so allow

        agent_policies = agent_conf.get("policies", {})
        allowed_commands = agent_policies.get("allowed_commands")

        # If a whitelist is defined and not empty, the command must be on it.
        if allowed_commands:
            command_base = command.strip().split()[0]
            if command_base not in allowed_commands:
                print(f"Security: Denied command for agent '{agent_name}' not in whitelist: {command}")
                return False
        
        return True

    def start(self):
        """Start the daemon server."""
        if self.use_tcp:
            # TCP socket for cross-platform support
            self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket_server.bind((self.tcp_host, self.tcp_port))
            self.socket_server.listen(5)
            
            self.running = True
            print(f"LIKU Daemon listening on {self.tcp_host}:{self.tcp_port}")
        else:
            # UNIX socket for Unix/Linux/macOS
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
            
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
                if self.running:  # Only print if not intentionally stopping
                    print(f"Error accepting connection: {e}")
        
        self.stop()
    
    def stop(self):
        """Stop the daemon server."""
        self.running = False
        
        if self.socket_server:
            try:
                self.socket_server.close()
            except Exception:
                pass
        
        if self.socket_path and os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except Exception:
                pass
        
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
        
        # Tmux-specific operations (temporary direct access)
        elif action == "list_sessions":
            return self._list_sessions()
        
        elif action == "list_panes":
            return self._list_panes(request)
        
        # Sandbox operations
        elif action == "create_pane": # Legacy name, now means create_sandbox_resource
            return self._create_sandbox_resource(request)
        
        elif action == "kill_pane": # Legacy name
            return self._kill_sandbox_resource(request)
        
        elif action == "send_keys":
            return self._send_keys(request)
        
        elif action == "capture_pane": # Legacy name
            return self._capture_sandbox_output(request)
        
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
    
    # Tmux-specific handlers (leaky abstraction for now)
    
    def _list_sessions(self) -> Dict[str, Any]:
        """List tmux sessions."""
        # This is a tmux-specific operation. We instantiate the backend directly.
        tmux_sandbox = TmuxSandbox(self.event_bus)
        sessions = tmux_sandbox.tmux_manager.list_sessions()
        
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
        # This is a tmux-specific operation.
        session = request.get("session")
        tmux_sandbox = TmuxSandbox(self.event_bus)
        panes = tmux_sandbox.tmux_manager.list_panes(session)
        
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

    # Sandbox handlers

    def _create_sandbox_resource(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Create a resource in the appropriate sandbox."""
        agent_name = request.get("agent_name")
        session_key = request.get("session") # 'session' is the legacy key for session_key
        command = request.get("command")

        if not agent_name or not session_key:
            return {"status": "error", "error": "Missing 'agent_name' or 'session'"}

        # Start with the base config from agents.yaml
        agent_config = self.agent_configs.get(agent_name, {}).copy()

        # Load agent.json and merge its settings
        try:
            agent_json_path = Path(__file__).parent.parent / "agents" / agent_name / "agent.json"
            if agent_json_path.exists():
                with open(agent_json_path, 'r') as f:
                    agent_json_config = json.load(f)
                
                # Merge policies, with agent.json taking precedence
                if "policies" in agent_json_config:
                    agent_config.setdefault("policies", {}).update(agent_json_config["policies"])

        except Exception as e:
            print(f"Warning: Could not load or parse agent.json for '{agent_name}': {e}")

        sandbox = SandboxFactory.get_sandbox(agent_config, self.global_policies, self.event_bus)

        try:
            resource = sandbox.create(
                agent_name=agent_name,
                session_key=session_key,
                command=command,
                config=agent_config
            )
            return {"status": "ok", "pane": {"pane_id": resource.id, "pane_pid": resource.pid}}
        except Exception as e:
            return {"status": "error", "error": f"Failed to create sandbox resource: {e}"}

    def _kill_sandbox_resource(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Kill/destroy a sandbox resource."""
        pane_id = request.get("pane_id") # Legacy name
        if not pane_id:
            return {"status": "error", "error": "Missing 'pane_id'"}

        session = self.state_backend.get_agent_session_by_pane_id(pane_id)
        agent_name = session.get("agent_name") if session else None
        agent_config = self.agent_configs.get(agent_name, {}) if agent_name else {}
        
        sandbox = SandboxFactory.get_sandbox(agent_config, self.global_policies, self.event_bus)
        
        try:
            sandbox.kill(resource_id=pane_id, agent_name=agent_name)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to kill sandbox resource: {e}"}

    def _send_keys(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send keys to a resource, with security validation."""
        pane_id = request.get("pane_id")
        keys = request.get("keys")
        literal = request.get("literal", False)
        
        if not pane_id or not keys:
            return {"status": "error", "error": "Missing 'pane_id' or 'keys'"}

        # Security Validation
        session = self.state_backend.get_agent_session_by_pane_id(pane_id)
        agent_name = session.get("agent_name") if session else None
        if not self._is_command_allowed(agent_name, keys):
            return {"status": "error", "error": f"Command denied by security policy for agent '{agent_name}': {keys}"}
        
        # Get sandbox and execute
        agent_config = self.agent_configs.get(agent_name, {}) if agent_name else {}
        sandbox = SandboxFactory.get_sandbox(agent_config, self.global_policies, self.event_bus)
        
        try:
            sandbox.execute(resource_id=pane_id, command=keys, literal=literal)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": f"Failed to send keys to sandbox resource: {e}"}

    def _capture_sandbox_output(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Capture output from a sandbox resource."""
        pane_id = request.get("pane_id")
        lines = request.get("start", -50) # Legacy key
        
        if not pane_id:
            return {"status": "error", "error": "Missing 'pane_id'"}
        
        session = self.state_backend.get_agent_session_by_pane_id(pane_id)
        agent_name = session.get("agent_name") if session else None
        agent_config = self.agent_configs.get(agent_name, {}) if agent_name else {}

        sandbox = SandboxFactory.get_sandbox(agent_config, self.global_policies, self.event_bus)

        try:
            # The 'start' parameter in the old API was negative, so we make it positive for 'lines'
            output = sandbox.capture_output(resource_id=pane_id, lines=abs(lines))
            return {"status": "ok", "output": output}
        except Exception as e:
            return {"status": "error", "error": f"Failed to capture sandbox output: {e}"}

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
