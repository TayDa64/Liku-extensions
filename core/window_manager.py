#!/usr/bin/env python3
"""
Cross-platform implementation of window management operations.
"""

import json
import re
import subprocess
import platform
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
import sys

from core.event_bus import EventBus 


@dataclass
class Pane:
    """Represents a terminal pane/window."""
    session: str
    window_index: int
    pane_index: int
    pane_id: str
    pane_pid: int
    pane_current_command: str
    pane_width: int
    pane_height: int

@dataclass
class Session:
    """Represents a terminal session."""
    name: str
    windows: int
    attached: bool
    created: str

class WindowManager:
    """
    Abstract base class for window management operations.
    """
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or EventBus()
        self._check_availability()

    def _check_availability(self):
        raise NotImplementedError

    def list_sessions(self) -> List[Session]:
        raise NotImplementedError

    def list_panes(self, session: Optional[str] = None) -> List[Pane]:
        raise NotImplementedError

    def create_pane(
        self,
        session: str,
        command: Optional[List[str]] = None,
        agent_name: Optional[str] = None
    ) -> Optional[Pane]:
        raise NotImplementedError

    def kill_pane(self, pane_id: str, agent_name: Optional[str] = None):
        raise NotImplementedError

    def ensure_session(self, session_name: str) -> bool:
        raise NotImplementedError

class TmuxWindowManager(WindowManager):
    """
    Manager for tmux operations with event emission.
    """
    def _check_availability(self):
        try:
            subprocess.run(["tmux", "-V"], capture_output=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            raise RuntimeError("tmux is not available or not responding")

    def _run_tmux(self, args: List[str]) -> str:
        result = subprocess.run(["tmux"] + args, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"tmux command failed: {result.stderr}")
        return result.stdout.strip()

    def list_sessions(self) -> List[Session]:
        try:
            output = self._run_tmux(["list-sessions", "-F", "#{session_name}|#{session_windows}|#{session_attached}|#{session_created}"])
        except RuntimeError:
            return []
        
        sessions = []
        for line in output.splitlines():
            if not line: continue
            parts = line.split("|")
            if len(parts) >= 4:
                sessions.append(Session(name=parts[0], windows=int(parts[1]), attached=parts[2] == "1", created=parts[3]))
        return sessions

    def list_panes(self, session: Optional[str] = None) -> List[Pane]:
        target = f"-t {session}" if session else "-a"
        try:
            output = self._run_tmux(["list-panes", target, "-F", "#{session_name}|#{window_index}|#{pane_index}|#{pane_id}|#{pane_pid}|#{pane_current_command}|#{pane_width}|#{pane_height}"])
        except RuntimeError:
            return []
        
        panes = []
        for line in output.splitlines():
            if not line: continue
            parts = line.split("|")
            if len(parts) >= 8:
                panes.append(Pane(session=parts[0], window_index=int(parts[1]), pane_index=int(parts[2]), pane_id=parts[3], pane_pid=int(parts[4]), pane_current_command=parts[5], pane_width=int(parts[6]), pane_height=int(parts[7])))
        return panes

    def create_pane(self, session: str, command: Optional[List[str]] = None, agent_name: Optional[str] = None) -> Optional[Pane]:
        cmd = ["split-window", "-h", "-t", session, "-P", "-F", "#{pane_id}"]
        if command:
            cmd.extend(command)
        
        pane_id = self._run_tmux(cmd)
        panes = self.list_panes(session)
        created_pane = next((p for p in panes if p.pane_id == pane_id), None)
        
        if created_pane:
            self.event_bus.emit("agent.spawn", payload={"agent_name": agent_name or "unknown", "pane_id": pane_id, "session": session, "command": " ".join(command or [])})
        
        return created_pane

    def kill_pane(self, pane_id: str, agent_name: Optional[str] = None):
        self._run_tmux(["kill-pane", "-t", pane_id])
        self.event_bus.emit("agent.kill", payload={"agent_name": agent_name or "unknown", "pane_id": pane_id})

    def ensure_session(self, session_name: str) -> bool:
        if any(s.name == session_name for s in self.list_sessions()):
            return False
        self._run_tmux(["new-session", "-d", "-s", session_name])
        return True

import os

import tempfile
from pathlib import Path

class WindowsWindowManager(WindowManager):
    """
    Manager for Windows Terminal operations.
    This is a simplified implementation focusing on spawning new agent windows.
    """
    def _check_availability(self):
        try:
            subprocess.run(["wt.exe", "-v"], capture_output=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            raise RuntimeError("Windows Terminal (wt.exe) is not available or not in your PATH.")

    def list_sessions(self) -> List[Session]:
        print("Warning: Session listing is not implemented for Windows.")
        return [Session(name="default", windows=1, attached=True, created="")]

    def list_panes(self, session: Optional[str] = None) -> List[Pane]:
        print("Warning: Pane listing is not implemented for Windows.")
        return []

    def create_pane(self, session: str, command: Optional[List[str]] = None, agent_name: Optional[str] = None) -> Optional[Pane]:
        if not command:
            raise ValueError("Command must be provided to create a window on Windows.")

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Convert the command list to a properly quoted command line string for cmd.exe
        command_line_string = subprocess.list2cmdline(command)

        # This is the robust command structure based on wt.exe documentation.
        # It sets the directory natively and passes a single command string to cmd /k.
        final_command = [
            "wt.exe",
            "new-tab",
            "--title", agent_name or "Agent",
            "--startingDirectory", project_root,
            "cmd", "/k", command_line_string
        ]

        proc = subprocess.Popen(final_command)
        
        pane_id = f"win_{proc.pid}"
        self.event_bus.emit("agent.spawn", payload={"agent_name": agent_name or "unknown", "pane_id": pane_id, "session": session, "command": " ".join(command)})
        
        return Pane(
            session=session,
            window_index=0,
            pane_index=proc.pid,
            pane_id=pane_id,
            pane_pid=proc.pid,
            pane_current_command=" ".join(command),
            pane_width=120,
            pane_height=30
        )

    def kill_pane(self, pane_id: str, agent_name: Optional[str] = None):
        try:
            pid = int(pane_id.split('_')[1])
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)])
            self.event_bus.emit("agent.kill", payload={"agent_name": agent_name or "unknown", "pane_id": pane_id})
        except (IndexError, ValueError) as e:
            print(f"Error killing pane {pane_id}: Invalid ID format. {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error killing process for pane {pane_id}: {e}", file=sys.stderr)

    def ensure_session(self, session_name: str) -> bool:
        print(f"Info: Ensuring session '{session_name}' (no-op on Windows).")
        return False


def get_window_manager(event_bus: Optional[EventBus] = None) -> WindowManager:
    """
    Factory function to get the appropriate window manager for the current OS.
    """
    os_type = platform.system()
    if os_type == "Windows":
        return WindowsWindowManager(event_bus)
    elif os_type in ["Linux", "Darwin"]:
        return TmuxWindowManager(event_bus)
    else:
        raise RuntimeError(f"Unsupported operating system: {os_type}")

def main():
    """CLI entry point for window manager operations."""
    manager = get_window_manager()
    
    if len(sys.argv) < 2:
        print("Usage: window_manager.py <command> [args...]")
        # Add more specific usage instructions here if needed
        sys.exit(1)

    command = sys.argv[1]
    
    if command == "list-sessions":
        sessions = manager.list_sessions()
        for session in sessions:
            print(f"{session.name}: {session.windows} windows, attached={session.attached}")
    
    elif command == "list-panes":
        session = sys.argv[2] if len(sys.argv) > 2 else None
        panes = manager.list_panes(session)
        for pane in panes:
            print(f"{pane.pane_id} ({pane.session}:{pane.window_index}.{pane.pane_index}) - {pane.pane_current_command} [PID {pane.pane_pid}]")
    
    # Add other command handlers as needed

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
