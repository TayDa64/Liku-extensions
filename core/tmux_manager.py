#!/usr/bin/env python3
"""
Python implementation of tmux management operations.
Replaces tmux-agent.sh with structured OOP approach.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

from liku.event_bus import EventBus


@dataclass
class TmuxPane:
    """Represents a tmux pane."""
    session: str
    window_index: int
    pane_index: int
    pane_id: str
    pane_pid: int
    pane_current_command: str
    pane_width: int
    pane_height: int


@dataclass
class TmuxSession:
    """Represents a tmux session."""
    name: str
    windows: int
    attached: bool
    created: str


class TmuxManager:
    """
    Manager for tmux operations with event emission.
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize tmux manager.
        
        Args:
            event_bus: Optional EventBus instance for event emission
        """
        self.event_bus = event_bus or EventBus()
        self._check_tmux_available()
    
    def _check_tmux_available(self):
        """Check if tmux is available."""
        try:
            subprocess.run(
                ["tmux", "-V"],
                capture_output=True,
                check=True,
                timeout=5
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            raise RuntimeError("tmux is not available or not responding")
    
    def _run_tmux(self, args: List[str]) -> str:
        """
        Run a tmux command.
        
        Args:
            args: Command arguments
            
        Returns:
            Command output
        """
        result = subprocess.run(
            ["tmux"] + args,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"tmux command failed: {result.stderr}")
        
        return result.stdout.strip()
    
    def list_sessions(self) -> List[TmuxSession]:
        """
        List all tmux sessions.
        
        Returns:
            List of TmuxSession objects
        """
        try:
            output = self._run_tmux([
                "list-sessions",
                "-F",
                "#{session_name}|#{session_windows}|#{session_attached}|#{session_created}"
            ])
        except RuntimeError:
            return []
        
        sessions = []
        for line in output.splitlines():
            if not line:
                continue
            
            parts = line.split("|")
            if len(parts) >= 4:
                sessions.append(TmuxSession(
                    name=parts[0],
                    windows=int(parts[1]),
                    attached=parts[2] == "1",
                    created=parts[3]
                ))
        
        return sessions
    
    def list_panes(self, session: Optional[str] = None) -> List[TmuxPane]:
        """
        List all tmux panes.
        
        Args:
            session: Optional session name to filter by
            
        Returns:
            List of TmuxPane objects
        """
        target = f"-t {session}" if session else "-a"
        
        try:
            output = self._run_tmux([
                "list-panes",
                target,
                "-F",
                "#{session_name}|#{window_index}|#{pane_index}|#{pane_id}|#{pane_pid}|#{pane_current_command}|#{pane_width}|#{pane_height}"
            ])
        except RuntimeError:
            return []
        
        panes = []
        for line in output.splitlines():
            if not line:
                continue
            
            parts = line.split("|")
            if len(parts) >= 8:
                panes.append(TmuxPane(
                    session=parts[0],
                    window_index=int(parts[1]),
                    pane_index=int(parts[2]),
                    pane_id=parts[3],
                    pane_pid=int(parts[4]),
                    pane_current_command=parts[5],
                    pane_width=int(parts[6]),
                    pane_height=int(parts[7])
                ))
        
        return panes
    
    def create_pane(
        self,
        session: str,
        command: Optional[str] = None,
        vertical: bool = False,
        agent_name: Optional[str] = None
    ) -> TmuxPane:
        """
        Create a new tmux pane.
        
        Args:
            session: Session name
            command: Optional command to run in pane
            vertical: If True, split vertically; otherwise horizontally
            agent_name: Optional agent name for event tracking
            
        Returns:
            Created TmuxPane object
        """
        split_flag = "-v" if vertical else "-h"
        
        # Build command
        cmd = ["split-window", split_flag, "-t", session, "-P", "-F", "#{pane_id}"]
        if command:
            cmd.extend([command])
        
        pane_id = self._run_tmux(cmd)
        
        # Get pane details
        panes = self.list_panes(session)
        created_pane = next((p for p in panes if p.pane_id == pane_id), None)
        
        if created_pane:
            # Emit event
            self.event_bus.emit(
                "agent.spawn",
                payload={
                    "agent_name": agent_name or "unknown",
                    "pane_id": pane_id,
                    "session": session,
                    "command": command
                }
            )
        
        return created_pane
    
    def kill_pane(self, pane_id: str, agent_name: Optional[str] = None):
        """
        Kill a tmux pane.
        
        Args:
            pane_id: Pane ID to kill
            agent_name: Optional agent name for event tracking
        """
        self._run_tmux(["kill-pane", "-t", pane_id])
        
        # Emit event
        self.event_bus.emit(
            "agent.kill",
            payload={
                "agent_name": agent_name or "unknown",
                "pane_id": pane_id
            }
        )
    
    def send_keys(self, pane_id: str, keys: str, literal: bool = False):
        """
        Send keys to a tmux pane.
        
        Args:
            pane_id: Target pane ID
            keys: Keys to send
            literal: If True, send keys literally without Enter
        """
        cmd = ["send-keys", "-t", pane_id]
        if literal:
            cmd.append("-l")
        cmd.append(keys)
        
        if not literal:
            cmd.append("Enter")
        
        self._run_tmux(cmd)
    
    def capture_pane(self, pane_id: str, start: int = -50) -> str:
        """
        Capture pane output.
        
        Args:
            pane_id: Pane ID to capture
            start: Starting line number (negative for history)
            
        Returns:
            Captured output
        """
        return self._run_tmux([
            "capture-pane",
            "-t", pane_id,
            "-p",
            "-S", str(start)
        ])
    
    def ensure_session(self, session_name: str) -> bool:
        """
        Ensure a tmux session exists.
        
        Args:
            session_name: Name of session to ensure
            
        Returns:
            True if session was created, False if it already existed
        """
        sessions = self.list_sessions()
        if any(s.name == session_name for s in sessions):
            return False
        
        self._run_tmux(["new-session", "-d", "-s", session_name])
        return True
    
    def get_orphaned_panes(self) -> List[TmuxPane]:
        """
        Find orphaned panes (no active agent process).
        
        Returns:
            List of orphaned TmuxPane objects
        """
        import psutil
        
        orphaned = []
        for pane in self.list_panes():
            try:
                # Check if the pane's PID is still running
                process = psutil.Process(pane.pane_pid)
                
                # Check if it's a shell with no children (potential orphan)
                if pane.pane_current_command in ["bash", "sh", "zsh"] and not process.children():
                    orphaned.append(pane)
            
            except psutil.NoSuchProcess:
                # PID doesn't exist, definitely orphaned
                orphaned.append(pane)
        
        return orphaned


def main():
    """CLI entry point for tmux operations."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  tmux_manager.py list-sessions")
        print("  tmux_manager.py list-panes [session]")
        print("  tmux_manager.py create-pane <session> [command]")
        print("  tmux_manager.py kill-pane <pane_id>")
        print("  tmux_manager.py capture <pane_id>")
        sys.exit(1)
    
    manager = TmuxManager()
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
    
    elif command == "create-pane":
        if len(sys.argv) < 3:
            print("Usage: tmux_manager.py create-pane <session> [command]")
            sys.exit(1)
        
        session = sys.argv[2]
        cmd = sys.argv[3] if len(sys.argv) > 3 else None
        
        pane = manager.create_pane(session, cmd)
        print(f"Created pane: {pane.pane_id}")
    
    elif command == "kill-pane":
        if len(sys.argv) < 3:
            print("Usage: tmux_manager.py kill-pane <pane_id>")
            sys.exit(1)
        
        pane_id = sys.argv[2]
        manager.kill_pane(pane_id)
        print(f"Killed pane: {pane_id}")
    
    elif command == "capture":
        if len(sys.argv) < 3:
            print("Usage: tmux_manager.py capture <pane_id>")
            sys.exit(1)
        
        pane_id = sys.argv[2]
        output = manager.capture_pane(pane_id)
        print(output)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
